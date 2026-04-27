#include "AegisChatApp.h"

#include "Json.h"
#include "imgui.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace aegis {
namespace {

template <size_t N>
void SetBuffer(std::array<char, N>& buffer, const std::string& value)
{
    buffer.fill('\0');
    const size_t count = std::min(N - 1, value.size());
    std::memcpy(buffer.data(), value.data(), count);
}

std::string BufferString(const char* buffer)
{
    return Trim(std::string(buffer == nullptr ? "" : buffer));
}

ImVec4 StatusColor(bool ok)
{
    return ok ? ImVec4(0.25f, 0.86f, 0.68f, 1.0f) : ImVec4(0.94f, 0.36f, 0.36f, 1.0f);
}

void TextMuted(const char* text)
{
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.58f, 0.64f, 0.68f, 1.0f));
    ImGui::TextWrapped("%s", text);
    ImGui::PopStyleColor();
}

void TextMuted(const std::string& text)
{
    TextMuted(text.c_str());
}

void Pill(const char* label, const ImVec4& color)
{
    ImGui::PushStyleColor(ImGuiCol_Text, color);
    ImGui::TextUnformatted(label);
    ImGui::PopStyleColor();
}

bool ContainsCaseInsensitive(const std::string& text, const std::string& needle)
{
    if (needle.empty()) {
        return true;
    }
    return Lower(text).find(Lower(needle)) != std::string::npos;
}

bool ContainsAnyTerm(const std::string& lowered, const std::vector<std::string>& terms)
{
    for (const std::string& term : terms) {
        if (lowered.find(term) != std::string::npos) {
            return true;
        }
    }
    return false;
}

std::string ExtractWindowsPathFromPrompt(const std::string& text)
{
    for (size_t i = 0; i + 2 < text.size(); ++i) {
        const unsigned char drive = static_cast<unsigned char>(text[i]);
        if (!std::isalpha(drive) || text[i + 1] != ':' || (text[i + 2] != '\\' && text[i + 2] != '/')) {
            continue;
        }

        size_t end = i + 3;
        while (end < text.size()) {
            const char ch = text[end];
            if (ch == '\r' || ch == '\n' || ch == '"' || ch == '\'' || ch == '`' || ch == '<' || ch == '>' || ch == '|' || ch == '*' || ch == '?') {
                break;
            }
            ++end;
        }

        std::string candidate = Trim(text.substr(i, end - i));
        const std::string lowered = Lower(candidate);
        size_t stop = std::string::npos;
        const std::vector<std::string> stop_phrases = {
            " please", " and then ", " then ", " so ", " but ", " because ", " with ", " using ", " for me", " if "
        };
        for (const std::string& phrase : stop_phrases) {
            const size_t found = lowered.find(phrase, 3);
            if (found != std::string::npos) {
                stop = std::min(stop, found);
            }
        }
        if (stop != std::string::npos) {
            candidate = Trim(candidate.substr(0, stop));
        }

        while (!candidate.empty()) {
            const char tail = candidate.back();
            if (tail != '.' && tail != ',' && tail != ';' && tail != ')' && tail != ']' && tail != '}') {
                break;
            }
            candidate.pop_back();
            candidate = Trim(candidate);
        }
        return candidate;
    }
    return {};
}

bool ShouldAutoApplyPrompt(const std::string& text)
{
    const std::string lowered = Lower(text);
    const std::vector<std::string> action_terms = {
        "create", "build", "make", "generate", "scaffold", "write", "add", "implement", "set up", "setup"
    };
    const std::vector<std::string> artifact_terms = {
        "website", "web site", "app", "page", "file", "project", "component", "dashboard", "api", "script",
        "template", "tool", "folder"
    };
    const std::vector<std::string> read_only_terms = {
        "review", "explain", "summarize", "analyze", "look at", "what is", "why"
    };

    const bool wants_files = ContainsAnyTerm(lowered, action_terms) && ContainsAnyTerm(lowered, artifact_terms);
    if (!wants_files) {
        return false;
    }
    return !ContainsAnyTerm(lowered, read_only_terms) || lowered.find("create") != std::string::npos ||
        lowered.find("build") != std::string::npos || lowered.find("make") != std::string::npos;
}

std::string NormalizePatchPath(std::string path);

std::string PathFromActionEntry(const std::string& entry)
{
    std::string path = entry;
    const size_t colon = path.find(':');
    if (colon != std::string::npos) {
        path = path.substr(colon + 1);
    }
    return path;
}

bool AppliedEntryMatchesChange(const std::string& entry, const FileChange& change)
{
    return Lower(NormalizePatchPath(Trim(PathFromActionEntry(entry)))) == Lower(NormalizePatchPath(Trim(change.path)));
}

bool ChangeAlreadyApplied(const AgentResponse& response, const FileChange& change)
{
    return std::any_of(response.applied.begin(), response.applied.end(), [&change](const std::string& entry) {
        return AppliedEntryMatchesChange(entry, change);
    });
}

int AppliedChangeCount(const AgentResponse& response)
{
    return static_cast<int>(std::count_if(response.changes.begin(), response.changes.end(), [&response](const FileChange& change) {
        return ChangeAlreadyApplied(response, change);
    }));
}

bool ResponseChangesFullyApplied(const AgentResponse& response)
{
    return !response.changes.empty() && AppliedChangeCount(response) >= static_cast<int>(response.changes.size());
}

void AppendUniqueAppliedEntries(std::vector<std::string>& target, const std::vector<std::string>& applied)
{
    for (const std::string& entry : applied) {
        if (std::find(target.begin(), target.end(), entry) == target.end()) {
            target.push_back(entry);
        }
    }
}

void RemoveAppliedEntriesForRestoredFiles(std::vector<std::string>& applied, const std::vector<std::string>& restored)
{
    std::vector<std::string> restored_paths;
    restored_paths.reserve(restored.size());
    for (const std::string& entry : restored) {
        restored_paths.push_back(Lower(NormalizePatchPath(Trim(PathFromActionEntry(entry)))));
    }

    applied.erase(
        std::remove_if(applied.begin(), applied.end(), [&restored_paths](const std::string& entry) {
            const std::string applied_path = Lower(NormalizePatchPath(Trim(PathFromActionEntry(entry))));
            return std::find(restored_paths.begin(), restored_paths.end(), applied_path) != restored_paths.end();
        }),
        applied.end());
}

std::string Shorten(const std::string& value, size_t max_len)
{
    if (value.size() <= max_len) {
        return value;
    }
    if (max_len <= 3) {
        return value.substr(0, max_len);
    }
    return value.substr(0, max_len - 3) + "...";
}

std::string CheckpointDisplayTime(const CheckpointSummaryInfo& checkpoint)
{
    if (checkpoint.created_at.size() >= 19) {
        std::string stamp = checkpoint.created_at.substr(0, 19);
        std::replace(stamp.begin(), stamp.end(), 'T', ' ');
        return stamp + " UTC";
    }
    if (checkpoint.id.size() >= 15) {
        return checkpoint.id.substr(0, 8) + " " + checkpoint.id.substr(9, 6) + " UTC";
    }
    return checkpoint.id;
}

bool ValidationPassed(const CommandRun& run)
{
    return run.allowed && !run.timed_out && run.has_exit_code && run.exit_code == 0;
}

bool ValidationFailed(const AgentResponse& response)
{
    return response.has_validation && !ValidationPassed(response.validation);
}

std::string ValidationCombinedOutput(const CommandRun& run)
{
    std::string output = run.stdout_text;
    if (!run.stderr_text.empty()) {
        if (!output.empty()) {
            output += "\n";
        }
        output += "[stderr]\n" + run.stderr_text;
    }
    return output;
}

std::string BuildValidationRepairPrompt(const AgentResponse& response)
{
    const CommandRun& validation = response.validation;
    const std::string output = Shorten(ValidationCombinedOutput(validation), 6000);

    std::ostringstream prompt;
    prompt << "Fix the current validation failure in this workspace. Inspect the relevant files, make the smallest safe patch, apply it, and run validation again.\n\n";
    prompt << "Validation command: " << (validation.command.empty() ? "[not provided]" : validation.command) << "\n";
    if (validation.has_exit_code) {
        prompt << "Exit code: " << validation.exit_code << "\n";
    }
    if (validation.timed_out) {
        prompt << "Timed out: true\n";
    }
    if (!validation.category.empty()) {
        prompt << "Failure category: " << validation.category << "\n";
    }
    if (!validation.summary.empty()) {
        prompt << "Failure summary: " << validation.summary << "\n";
    }
    if (!output.empty()) {
        prompt << "\nValidation output:\n" << output << "\n";
    }
    prompt << "\nUse checkpoints and rollback if a repair attempt makes validation worse.";
    return prompt.str();
}

bool IsCreativePreviewFormat(const std::string& format)
{
    const std::string lowered = Lower(format);
    return lowered == "png" || lowered == "jpg" || lowered == "jpeg" ||
        lowered == "webp" || lowered == "gif" || lowered == "svg" ||
        lowered == "html" || lowered == "wav" || lowered == "mp3" ||
        lowered == "midi" || lowered == "mid" || lowered == "psd";
}

bool IsRasterCreativePreviewFormat(const std::string& format)
{
    const std::string lowered = Lower(format);
    return lowered == "png" || lowered == "jpg" || lowered == "jpeg" ||
        lowered == "bmp" || lowered == "gif" || lowered == "tif" ||
        lowered == "tiff" || lowered == "webp";
}

bool IsCreativeAudioFormat(const std::string& format)
{
    const std::string lowered = Lower(format);
    return lowered == "wav" || lowered == "mp3" || lowered == "m4a" ||
        lowered == "aac" || lowered == "wma" || lowered == "midi" ||
        lowered == "mid";
}

std::string CreativeAssetLabel(const MediaAssetInfo& asset)
{
    const std::string format = Lower(asset.format);
    if (IsCreativeAudioFormat(format)) {
        return "Audio Preview";
    }
    if (format == "gif" || format == "html") {
        return "Motion Preview";
    }
    if (format == "psd" || format == "jsx") {
        return "Photoshop Package";
    }
    if (format == "svg") {
        return "Editable Vector";
    }
    if (format == "png" || format == "jpg" || format == "jpeg" || format == "webp") {
        return "Image Preview";
    }
    return asset.role.empty() ? "Asset Preview" : asset.role;
}

int BestCreativePreviewIndex(const std::vector<MediaAssetInfo>& assets)
{
    const char* preferred[] = { "png", "gif", "html", "svg", "wav", "mp3", "midi", "psd" };
    for (const char* format : preferred) {
        for (int i = 0; i < static_cast<int>(assets.size()); ++i) {
            if (Lower(assets[i].format) == format) {
                return i;
            }
        }
    }
    for (int i = 0; i < static_cast<int>(assets.size()); ++i) {
        if (IsCreativePreviewFormat(assets[i].format)) {
            return i;
        }
    }
    return assets.empty() ? -1 : 0;
}

std::string JoinPalette(const std::vector<std::string>& palette)
{
    std::ostringstream joined;
    for (size_t i = 0; i < palette.size(); ++i) {
        if (i > 0) {
            joined << ", ";
        }
        joined << palette[i];
    }
    return joined.str();
}

std::vector<std::string> SplitCommaList(const std::string& value)
{
    std::vector<std::string> out;
    std::stringstream stream(value);
    std::string item;
    while (std::getline(stream, item, ',')) {
        item = Trim(item);
        if (!item.empty() && std::find(out.begin(), out.end(), item) == out.end()) {
            out.push_back(item);
        }
    }
    return out;
}

std::string WorkspacePathLower(std::string path)
{
    std::replace(path.begin(), path.end(), '\\', '/');
    return Lower(path);
}

bool HasNamedWorkspaceFile(const std::vector<WorkspaceFile>& files, std::initializer_list<const char*> names)
{
    for (const WorkspaceFile& file : files) {
        const std::string path = WorkspacePathLower(file.path);
        for (const char* raw_name : names) {
            const std::string name = WorkspacePathLower(raw_name == nullptr ? "" : raw_name);
            if (!name.empty() && (path == name || path.ends_with("/" + name))) {
                return true;
            }
        }
    }
    return false;
}

std::string FirstNamedWorkspaceFile(const std::vector<WorkspaceFile>& files, std::initializer_list<const char*> names)
{
    for (const WorkspaceFile& file : files) {
        const std::string path = WorkspacePathLower(file.path);
        for (const char* raw_name : names) {
            const std::string name = WorkspacePathLower(raw_name == nullptr ? "" : raw_name);
            if (!name.empty() && (path == name || path.ends_with("/" + name))) {
                return file.path;
            }
        }
    }
    return {};
}

std::string FirstWorkspaceFileWithExtension(const std::vector<WorkspaceFile>& files, const std::string& extension)
{
    const std::string lowered_ext = Lower(extension);
    for (const WorkspaceFile& file : files) {
        if (WorkspacePathLower(file.path).ends_with(lowered_ext)) {
            return file.path;
        }
    }
    return {};
}

bool HasWorkspaceFileWithExtension(const std::vector<WorkspaceFile>& files, const std::string& extension)
{
    return !FirstWorkspaceFileWithExtension(files, extension).empty();
}

bool HasWorkspacePathContaining(const std::vector<WorkspaceFile>& files, const std::string& needle)
{
    const std::string lowered = WorkspacePathLower(needle);
    for (const WorkspaceFile& file : files) {
        if (!lowered.empty() && WorkspacePathLower(file.path).find(lowered) != std::string::npos) {
            return true;
        }
    }
    return false;
}

std::string QuoteCommandPath(const std::string& path)
{
    if (path.empty()) {
        return path;
    }
    return "\"" + path + "\"";
}

void AddValidationSuggestion(
    std::vector<ValidationSuggestionInfo>& suggestions,
    const std::string& command,
    const std::string& label,
    const std::string& category,
    const std::string& reason)
{
    const std::string trimmed = Trim(command);
    if (trimmed.empty()) {
        return;
    }
    for (const ValidationSuggestionInfo& existing : suggestions) {
        if (Lower(existing.command) == Lower(trimmed)) {
            return;
        }
    }
    suggestions.push_back({trimmed, label.empty() ? trimmed : label, category, reason});
}

std::string NodePackageManager(const std::vector<WorkspaceFile>& files)
{
    if (HasNamedWorkspaceFile(files, {"pnpm-lock.yaml", "pnpm-workspace.yaml"})) {
        return "pnpm";
    }
    if (HasNamedWorkspaceFile(files, {"yarn.lock"})) {
        return "yarn";
    }
    return "npm";
}

std::string NodeRunCommand(const std::string& manager, const std::string& script)
{
    if (manager == "pnpm" || manager == "yarn") {
        return manager + " " + script;
    }
    return script == "test" ? "npm test" : "npm run " + script;
}

std::string NodeExecCommand(const std::string& manager, const std::string& command)
{
    if (manager == "pnpm") {
        return "pnpm exec " + command;
    }
    if (manager == "yarn") {
        return "yarn " + command;
    }
    return "npx " + command;
}

std::vector<ValidationSuggestionInfo> BuildProjectValidationSuggestions(const std::vector<WorkspaceFile>& files)
{
    std::vector<ValidationSuggestionInfo> suggestions;
    if (files.empty()) {
        return suggestions;
    }

    if (HasNamedWorkspaceFile(files, {"package.json"})) {
        const std::string manager = NodePackageManager(files);
        AddValidationSuggestion(suggestions, NodeRunCommand(manager, "test"), "Node tests", "web/node", "package.json detected; run the project test script.");
        AddValidationSuggestion(suggestions, NodeRunCommand(manager, "build"), "Node build", "web/node", "Build the web app or Node package before shipping changes.");
        if (HasNamedWorkspaceFile(files, {"tsconfig.json"})) {
            AddValidationSuggestion(suggestions, NodeExecCommand(manager, "tsc --noEmit"), "TypeScript check", "web/node", "tsconfig.json detected; catch type errors without emitting files.");
        }
        if (HasNamedWorkspaceFile(files, {".eslintrc", ".eslintrc.json", ".eslintrc.js", "eslint.config.js", "eslint.config.mjs"})) {
            AddValidationSuggestion(suggestions, NodeRunCommand(manager, "lint"), "Lint", "web/node", "ESLint config detected; run lint for UI/API quality checks.");
        }
    }

    if (HasNamedWorkspaceFile(files, {"pyproject.toml", "pytest.ini", "requirements.txt", "setup.py"})) {
        if (HasNamedWorkspaceFile(files, {"pytest.ini"}) || HasWorkspacePathContaining(files, "tests/") || HasWorkspacePathContaining(files, "test_")) {
            AddValidationSuggestion(suggestions, "python -m pytest", "Python tests", "python", "Python test files or pytest config detected.");
        }
        AddValidationSuggestion(suggestions, "python -m compileall .", "Python syntax check", "python", "Fast syntax validation for Python projects.");
    }

    const std::string solution = FirstWorkspaceFileWithExtension(files, ".sln");
    const bool has_vcxproj = HasWorkspaceFileWithExtension(files, ".vcxproj");
    const bool has_csproj = HasWorkspaceFileWithExtension(files, ".csproj");
    if (HasNamedWorkspaceFile(files, {"build.ps1"})) {
        AddValidationSuggestion(suggestions, "powershell -ExecutionPolicy Bypass -File .\\build.ps1", "PowerShell build", "windows", "Workspace build.ps1 detected; use the project-owned build entrypoint.");
    }
    if (!solution.empty() && has_vcxproj) {
        AddValidationSuggestion(suggestions, "msbuild " + QuoteCommandPath(solution) + " /p:Configuration=Release /p:Platform=x64", "Visual Studio build", "windows/cpp", "Solution and vcxproj detected; validate native Windows build output.");
    } else if (!solution.empty() && has_csproj) {
        AddValidationSuggestion(suggestions, "dotnet test " + QuoteCommandPath(solution), "dotnet tests", "dotnet", "Solution and C# project detected; run the .NET test target.");
    } else if (has_csproj) {
        AddValidationSuggestion(suggestions, "dotnet test", "dotnet tests", "dotnet", "C# project detected; run the .NET test target.");
    }

    if (HasNamedWorkspaceFile(files, {"CMakeLists.txt"})) {
        AddValidationSuggestion(suggestions, "cmake --build build --config Release", "CMake build", "cpp", "CMake project detected; validate the configured build folder.");
    }
    if (HasNamedWorkspaceFile(files, {"Cargo.toml"})) {
        AddValidationSuggestion(suggestions, "cargo test", "Rust tests", "rust", "Cargo project detected; run Rust unit and integration tests.");
    }
    if (HasNamedWorkspaceFile(files, {"go.mod"})) {
        AddValidationSuggestion(suggestions, "go test ./...", "Go tests", "go", "Go module detected; test all packages.");
    }
    if (HasNamedWorkspaceFile(files, {"pubspec.yaml"})) {
        AddValidationSuggestion(suggestions, "flutter test", "Flutter tests", "mobile/flutter", "Flutter project detected; run widget/unit tests.");
        AddValidationSuggestion(suggestions, "flutter analyze", "Flutter analyze", "mobile/flutter", "Run static analysis before device builds.");
    }
    if (HasNamedWorkspaceFile(files, {"gradlew", "gradlew.bat", "build.gradle", "settings.gradle"})) {
        AddValidationSuggestion(suggestions, ".\\gradlew test", "Gradle tests", "mobile/java", "Gradle project detected; run JVM/unit tests.");
    }
    if (HasNamedWorkspaceFile(files, {"Package.swift"})) {
        AddValidationSuggestion(suggestions, "swift test", "Swift tests", "macos/swift", "Swift package detected; run package tests.");
    }
    if (HasNamedWorkspaceFile(files, {"Makefile", "makefile"})) {
        AddValidationSuggestion(suggestions, "make test", "Make tests", "native", "Makefile detected; use the conventional test target if present.");
    }

    return suggestions;
}

std::string BuildValidationSuggestionContext(const std::vector<ValidationSuggestionInfo>& suggestions)
{
    if (suggestions.empty()) {
        return {};
    }
    std::ostringstream stream;
    stream << "Detected validation/test suggestions:\n";
    const int count = std::min(6, static_cast<int>(suggestions.size()));
    for (int i = 0; i < count; ++i) {
        stream << "- " << suggestions[i].label << ": " << suggestions[i].command
               << " (" << suggestions[i].reason << ")\n";
    }
    return stream.str();
}

struct ContextRisk {
    std::string severity;
    std::string source;
    std::string finding;
    std::string detail;
};

void AddContextRisk(
    std::vector<ContextRisk>& risks,
    const std::string& severity,
    const std::string& source,
    const std::string& finding,
    const std::string& detail)
{
    risks.push_back({severity, source, finding, detail});
}

bool ContainsAnyNeedle(const std::string& lowered, const std::vector<std::string>& needles)
{
    for (const std::string& needle : needles) {
        if (lowered.find(needle) != std::string::npos) {
            return true;
        }
    }
    return false;
}

std::vector<ContextRisk> ScanPathForContextRisks(const std::string& source, const std::string& path)
{
    std::vector<ContextRisk> risks;
    const std::string lowered = Lower(path);
    const std::vector<std::string> secret_paths = {
        ".env", "id_rsa", "id_ed25519", "credentials", "credential", "secret",
        "secrets", "token", "apikey", "api_key", "private-key", "private_key",
        ".pem", ".pfx", ".p12", ".key", "known_hosts", "cookies"
    };
    const std::vector<std::string> generated_or_cache = {
        "node_modules/", "\\node_modules\\", ".venv/", "\\.venv\\", "__pycache__",
        ".git/", "\\.git\\", "dist/", "\\dist\\", "build/", "\\build\\",
        "x64/release", "x64\\release", ".cache", "logs/"
    };

    if (ContainsAnyNeedle(lowered, secret_paths)) {
        AddContextRisk(risks, "High", source, "Sensitive path", "File path looks like it may contain credentials, secrets, keys, or tokens.");
    } else if (ContainsAnyNeedle(lowered, generated_or_cache)) {
        AddContextRisk(risks, "Low", source, "Noisy path", "Generated, cached, or dependency paths usually should stay out of model context.");
    }
    return risks;
}

std::vector<ContextRisk> ScanTextForContextRisks(const std::string& source, const std::string& text)
{
    std::vector<ContextRisk> risks;
    const std::string lowered = Lower(text);
    const std::vector<std::string> prompt_injection = {
        "ignore previous instructions",
        "ignore all previous instructions",
        "disregard previous instructions",
        "forget previous instructions",
        "reveal your system prompt",
        "print your system prompt",
        "developer message",
        "system message",
        "hidden instructions",
        "do not tell the user",
        "override your instructions",
        "you are now"
    };
    const std::vector<std::string> secret_markers = {
        "begin rsa private key",
        "begin openssh private key",
        "begin private key",
        "authorization: bearer",
        "x-api-key",
        "api_key",
        "apikey",
        "secret_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "password=",
        "passwd=",
        "aws_secret_access_key",
        "github_token",
        "openai_api_key",
        "anthropic_api_key"
    };

    if (ContainsAnyNeedle(lowered, secret_markers)) {
        AddContextRisk(risks, "High", source, "Possible secret", "Text contains a common credential, token, key, or private-key marker.");
    }
    if (ContainsAnyNeedle(lowered, prompt_injection)) {
        AddContextRisk(risks, "Medium", source, "Prompt-injection phrase", "Text contains instructions that may be trying to override Aegis or model behavior.");
    }
    if (text.size() > 120000) {
        AddContextRisk(risks, "Medium", source, "Large attachment", "Very large context can bury the task, increase cost, and weaken answer quality.");
    }
    return risks;
}

std::filesystem::path ResolveWorkspacePath(const std::string& workspace_root, const std::string& path)
{
    std::filesystem::path candidate = Utf8ToWide(Trim(path));
    if (candidate.is_absolute()) {
        return candidate.lexically_normal();
    }
    const std::string root = Trim(workspace_root);
    if (root.empty()) {
        return candidate.lexically_normal();
    }
    return (std::filesystem::path(Utf8ToWide(root)) / candidate).lexically_normal();
}

std::filesystem::path ExistingParentOrSelf(std::filesystem::path path)
{
    std::error_code ec;
    while (!path.empty()) {
        if (std::filesystem::exists(path, ec)) {
            return path;
        }
        const std::filesystem::path parent = path.parent_path();
        if (parent == path) {
            break;
        }
        path = parent;
    }
    return {};
}

std::string NormalizePatchPath(std::string path)
{
    std::replace(path.begin(), path.end(), '\\', '/');
    while (!path.empty() && path.front() == '/') {
        path.erase(path.begin());
    }
    return path.empty() ? "untitled.txt" : path;
}

std::string ReadTextFileBestEffort(const std::filesystem::path& path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        return {};
    }
    return std::string((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
}

std::vector<std::string> SplitPatchLines(const std::string& text)
{
    std::vector<std::string> lines;
    std::istringstream stream(text);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        lines.push_back(line);
    }
    return lines;
}

struct InlineDiffLine {
    char marker = ' ';
    int old_line = 0;
    int new_line = 0;
    std::string text;
};

std::vector<InlineDiffLine> BuildGreedyDiffLines(
    const std::vector<std::string>& old_lines,
    const std::vector<std::string>& new_lines)
{
    std::vector<InlineDiffLine> diff;
    size_t old_index = 0;
    size_t new_index = 0;
    while (old_index < old_lines.size() || new_index < new_lines.size()) {
        if (old_index < old_lines.size() && new_index < new_lines.size() && old_lines[old_index] == new_lines[new_index]) {
            diff.push_back({' ', static_cast<int>(old_index + 1), static_cast<int>(new_index + 1), old_lines[old_index]});
            ++old_index;
            ++new_index;
            continue;
        }
        if (old_index < old_lines.size()) {
            diff.push_back({'-', static_cast<int>(old_index + 1), 0, old_lines[old_index]});
            ++old_index;
        }
        if (new_index < new_lines.size()) {
            diff.push_back({'+', 0, static_cast<int>(new_index + 1), new_lines[new_index]});
            ++new_index;
        }
    }
    return diff;
}

std::vector<InlineDiffLine> BuildInlineDiffLines(const FileChange& change, const std::string& workspace)
{
    const std::string action = Lower(Trim(change.action));
    std::string old_content;
    std::string new_content = change.has_content ? change.content : "";

    if (action != "create") {
        old_content = ReadTextFileBestEffort(ResolveWorkspacePath(workspace, change.path));
    }
    if (action == "delete") {
        new_content.clear();
    }

    const std::vector<std::string> old_lines = SplitPatchLines(old_content);
    const std::vector<std::string> new_lines = SplitPatchLines(new_content);
    std::vector<InlineDiffLine> diff;

    if ((action == "create" || old_content.empty()) && action != "delete") {
        for (size_t i = 0; i < new_lines.size(); ++i) {
            diff.push_back({'+', 0, static_cast<int>(i + 1), new_lines[i]});
        }
        return diff;
    }
    if (action == "delete") {
        for (size_t i = 0; i < old_lines.size(); ++i) {
            diff.push_back({'-', static_cast<int>(i + 1), 0, old_lines[i]});
        }
        return diff;
    }

    const size_t cells = (old_lines.size() + 1) * (new_lines.size() + 1);
    if (cells > 1200000) {
        return BuildGreedyDiffLines(old_lines, new_lines);
    }

    const size_t width = new_lines.size() + 1;
    std::vector<int> lcs((old_lines.size() + 1) * width, 0);
    auto at = [&](size_t i, size_t j) -> int& {
        return lcs[i * width + j];
    };

    for (size_t i = old_lines.size(); i-- > 0;) {
        for (size_t j = new_lines.size(); j-- > 0;) {
            if (old_lines[i] == new_lines[j]) {
                at(i, j) = at(i + 1, j + 1) + 1;
            } else {
                at(i, j) = std::max(at(i + 1, j), at(i, j + 1));
            }
        }
    }

    size_t old_index = 0;
    size_t new_index = 0;
    while (old_index < old_lines.size() || new_index < new_lines.size()) {
        if (old_index < old_lines.size() && new_index < new_lines.size() && old_lines[old_index] == new_lines[new_index]) {
            diff.push_back({' ', static_cast<int>(old_index + 1), static_cast<int>(new_index + 1), old_lines[old_index]});
            ++old_index;
            ++new_index;
        } else if (new_index < new_lines.size() &&
            (old_index >= old_lines.size() || at(old_index, new_index + 1) >= at(old_index + 1, new_index))) {
            diff.push_back({'+', 0, static_cast<int>(new_index + 1), new_lines[new_index]});
            ++new_index;
        } else if (old_index < old_lines.size()) {
            diff.push_back({'-', static_cast<int>(old_index + 1), 0, old_lines[old_index]});
            ++old_index;
        }
    }

    return diff;
}

int CountDiffMarker(const std::vector<InlineDiffLine>& diff, char marker)
{
    return static_cast<int>(std::count_if(diff.begin(), diff.end(), [marker](const InlineDiffLine& line) {
        return line.marker == marker;
    }));
}

struct SideBySideDiffRow {
    char marker = ' ';
    int old_line = 0;
    int new_line = 0;
    std::string old_text;
    std::string new_text;
};

std::vector<SideBySideDiffRow> BuildSideBySideDiffRows(const std::vector<InlineDiffLine>& diff)
{
    std::vector<SideBySideDiffRow> rows;
    for (size_t i = 0; i < diff.size(); ++i) {
        const InlineDiffLine& line = diff[i];
        if (line.marker == ' ') {
            rows.push_back({' ', line.old_line, line.new_line, line.text, line.text});
            continue;
        }
        if (line.marker == '-' && i + 1 < diff.size() && diff[i + 1].marker == '+') {
            const InlineDiffLine& next = diff[i + 1];
            rows.push_back({'!', line.old_line, next.new_line, line.text, next.text});
            ++i;
            continue;
        }
        if (line.marker == '-') {
            rows.push_back({'-', line.old_line, 0, line.text, ""});
            continue;
        }
        if (line.marker == '+') {
            rows.push_back({'+', 0, line.new_line, "", line.text});
        }
    }
    return rows;
}

struct DiffHunk {
    int index = 0;
    size_t start = 0;
    size_t end = 0;
    int old_start = 0;
    int new_start = 0;
    int added = 0;
    int removed = 0;
};

std::vector<DiffHunk> BuildDiffHunks(const std::vector<InlineDiffLine>& diff)
{
    std::vector<DiffHunk> hunks;
    size_t i = 0;
    while (i < diff.size()) {
        while (i < diff.size() && diff[i].marker == ' ') {
            ++i;
        }
        if (i >= diff.size()) {
            break;
        }

        DiffHunk hunk;
        hunk.index = static_cast<int>(hunks.size());
        hunk.start = i;
        while (i < diff.size() && diff[i].marker != ' ') {
            const InlineDiffLine& line = diff[i];
            if (hunk.old_start == 0 && line.old_line > 0) {
                hunk.old_start = line.old_line;
            }
            if (hunk.new_start == 0 && line.new_line > 0) {
                hunk.new_start = line.new_line;
            }
            if (line.marker == '+') {
                ++hunk.added;
            } else if (line.marker == '-') {
                ++hunk.removed;
            }
            ++i;
        }
        hunk.end = i;
        hunks.push_back(hunk);
    }
    return hunks;
}

std::string JoinPatchLines(const std::vector<std::string>& lines, bool trailing_newline)
{
    std::ostringstream joined;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (i > 0) {
            joined << "\n";
        }
        joined << lines[i];
    }
    if (trailing_newline && !lines.empty()) {
        joined << "\n";
    }
    return joined.str();
}

bool HasTrailingNewline(const std::string& text)
{
    return !text.empty() && (text.back() == '\n' || text.back() == '\r');
}

std::string ApplyOnlyHunkToContent(const std::vector<InlineDiffLine>& diff, const DiffHunk& hunk, bool trailing_newline)
{
    std::vector<std::string> lines;
    for (size_t i = 0; i < diff.size(); ++i) {
        const InlineDiffLine& line = diff[i];
        const bool selected = i >= hunk.start && i < hunk.end;
        if (line.marker == ' ') {
            lines.push_back(line.text);
        } else if (selected) {
            if (line.marker == '+') {
                lines.push_back(line.text);
            }
        } else if (line.marker == '-') {
            lines.push_back(line.text);
        }
    }
    return JoinPatchLines(lines, trailing_newline);
}

std::string HunkLabel(const DiffHunk& hunk)
{
    std::ostringstream label;
    label << "Hunk " << (hunk.index + 1) << "  -" << hunk.removed << " +" << hunk.added;
    if (hunk.old_start > 0 || hunk.new_start > 0) {
        label << "  old:" << (hunk.old_start > 0 ? std::to_string(hunk.old_start) : "-")
              << " new:" << (hunk.new_start > 0 ? std::to_string(hunk.new_start) : "-");
    }
    return label.str();
}

bool BuildSelectedHunkChange(
    const FileChange& change,
    const std::string& workspace,
    int hunk_index,
    FileChange& out_change,
    std::string& error)
{
    const std::string action = Lower(Trim(change.action));
    std::string old_content;
    if (action != "create") {
        old_content = ReadTextFileBestEffort(ResolveWorkspacePath(workspace, change.path));
    }

    const std::vector<InlineDiffLine> diff = BuildInlineDiffLines(change, workspace);
    const std::vector<DiffHunk> hunks = BuildDiffHunks(diff);
    if (hunks.empty()) {
        error = "No diff hunk is available for this generated change.";
        return false;
    }
    if (hunk_index < 0 || hunk_index >= static_cast<int>(hunks.size())) {
        error = "Selected hunk is out of range.";
        return false;
    }

    const bool trailing_newline = change.has_content ? HasTrailingNewline(change.content) : HasTrailingNewline(old_content);
    out_change = change;
    out_change.action = old_content.empty() && action == "create" ? "create" : "update";
    out_change.content = ApplyOnlyHunkToContent(diff, hunks[static_cast<size_t>(hunk_index)], trailing_newline);
    out_change.has_content = true;
    out_change.summary = "Apply " + HunkLabel(hunks[static_cast<size_t>(hunk_index)]) + " from: " + change.summary;
    return true;
}

std::string HunkRange(char sign, size_t count)
{
    if (count == 0) {
        return std::string(1, sign) + "0,0";
    }
    return std::string(1, sign) + "1," + std::to_string(count);
}

std::string BuildPatchText(const AgentResponse& response, const std::string& workspace)
{
    std::ostringstream patch;
    patch << "# Aegis generated patch package\n";
    patch << "# Task: " << response.task_id << "\n";
    if (!workspace.empty()) {
        patch << "# Workspace: " << workspace << "\n";
    }
    patch << "# Generated: " << NowTimeLabel() << "\n\n";

    for (const FileChange& change : response.changes) {
        const std::string path = NormalizePatchPath(change.path);
        const std::string action = Lower(Trim(change.action));
        std::string old_content;
        std::string new_content = change.has_content ? change.content : "";

        if (action != "create") {
            old_content = ReadTextFileBestEffort(ResolveWorkspacePath(workspace, change.path));
        }
        if (action == "delete") {
            new_content.clear();
        }

        const std::vector<std::string> old_lines = SplitPatchLines(old_content);
        const std::vector<std::string> new_lines = SplitPatchLines(new_content);
        const bool is_create = action == "create" || old_content.empty();
        const bool is_delete = action == "delete";

        patch << "diff --git a/" << path << " b/" << path << "\n";
        if (is_create && !is_delete) {
            patch << "new file mode 100644\n";
        } else if (is_delete) {
            patch << "deleted file mode 100644\n";
        }
        patch << "--- " << (is_create && !is_delete ? "/dev/null" : "a/" + path) << "\n";
        patch << "+++ " << (is_delete ? "/dev/null" : "b/" + path) << "\n";
        patch << "@@ " << HunkRange('-', old_lines.size()) << " " << HunkRange('+', new_lines.size()) << " @@\n";

        for (const std::string& line : old_lines) {
            patch << "-" << line << "\n";
        }
        for (const std::string& line : new_lines) {
            patch << "+" << line << "\n";
        }
        patch << "\n";
    }

    return patch.str();
}

bool EndsWith(const std::string& value, const std::string& suffix)
{
    return value.size() >= suffix.size() &&
        value.compare(value.size() - suffix.size(), suffix.size(), suffix) == 0;
}

bool ShouldToastStatus(const std::string& message)
{
    const std::string text = Trim(message);
    if (text.empty()) {
        return false;
    }
    const std::string lowered = Lower(text);
    if (EndsWith(text, "...") &&
        lowered.find("connecting") == std::string::npos &&
        lowered.find("saving") == std::string::npos &&
        lowered.find("creating") == std::string::npos &&
        lowered.find("validation") == std::string::npos) {
        return false;
    }

    const char* important[] = {
        "backend", "model", "settings", "saved", "ready", "connected", "offline", "failed",
        "error", "could not", "validation", "creative studio", "job", "applied", "copied",
        "opened", "recorded", "profile", "workspace", "changes", "route", "cancel", "context"
    };
    for (const char* term : important) {
        if (lowered.find(term) != std::string::npos) {
            return true;
        }
    }
    return lowered.find("new chat") != std::string::npos;
}

std::string ToastToneForStatus(const std::string& message)
{
    const std::string lowered = Lower(message);
    if (lowered.find("offline") != std::string::npos ||
        lowered.find("failed") != std::string::npos ||
        lowered.find("error") != std::string::npos ||
        lowered.find("could not") != std::string::npos ||
        lowered.find("denied") != std::string::npos ||
        lowered.find("timed out") != std::string::npos) {
        return "error";
    }
    if (lowered.find("saved") != std::string::npos ||
        lowered.find("ready") != std::string::npos ||
        lowered.find("connected") != std::string::npos ||
        lowered.find("finished") != std::string::npos ||
        lowered.find("applied") != std::string::npos ||
        lowered.find("copied") != std::string::npos ||
        lowered.find("opened") != std::string::npos ||
        lowered.find("recorded") != std::string::npos ||
        lowered.find("started") != std::string::npos ||
        lowered.find("loaded") != std::string::npos ||
        lowered.find("canceled") != std::string::npos) {
        return "success";
    }
    if (lowered.find("validation") != std::string::npos ||
        lowered.find("creating") != std::string::npos ||
        lowered.find("connecting") != std::string::npos ||
        lowered.find("saving") != std::string::npos) {
        return "working";
    }
    return "info";
}

std::string ToastTitleForStatus(const std::string& message)
{
    const std::string lowered = Lower(message);
    if (lowered.find("backend") != std::string::npos) {
        return "Backend";
    }
    if (lowered.find("model") != std::string::npos) {
        return "Model Stack";
    }
    if (lowered.find("validation") != std::string::npos) {
        return "Validation";
    }
    if (lowered.find("creative") != std::string::npos || lowered.find("studio") != std::string::npos || lowered.find("job") != std::string::npos) {
        return "Creative Studio";
    }
    if (lowered.find("settings") != std::string::npos || lowered.find("profile") != std::string::npos) {
        return "Settings";
    }
    if (lowered.find("copied") != std::string::npos) {
        return "Copied";
    }
    if (lowered.find("applied") != std::string::npos || lowered.find("changes") != std::string::npos) {
        return "Changes";
    }
    if (lowered.find("route") != std::string::npos) {
        return "Coding Route";
    }
    return "Aegis";
}

ImVec4 Rgba(float r, float g, float b, float a = 1.0f)
{
    return ImVec4(r / 255.0f, g / 255.0f, b / 255.0f, a);
}

ImU32 Color(float r, float g, float b, float a = 1.0f)
{
    return ImGui::GetColorU32(Rgba(r, g, b, a));
}

float Clamp01(float value)
{
    return std::max(0.0f, std::min(1.0f, value));
}

float EaseOutCubic(float value)
{
    const float t = 1.0f - Clamp01(value);
    return 1.0f - t * t * t;
}

float EaseInOut(float value)
{
    const float t = Clamp01(value);
    return t < 0.5f ? 2.0f * t * t : 1.0f - std::pow(-2.0f * t + 2.0f, 2.0f) * 0.5f;
}

float Pulse(float speed, float offset = 0.0f)
{
    return 0.5f + 0.5f * std::sin(static_cast<float>(ImGui::GetTime()) * speed + offset);
}

enum class IconGlyph {
    Shield,
    Plus,
    Chat,
    Explore,
    Agents,
    Documents,
    Tools,
    History,
    Search,
    Globe,
    Code,
    Document,
    Image,
    Sparkle,
    Attach,
    Sliders,
    Send,
    Copy,
    Like,
    Dislike,
    Regen,
    Chevron,
    Mail,
    Bolt,
};

IconGlyph CreativeAssetIcon(const MediaAssetInfo& asset)
{
    const std::string format = Lower(asset.format);
    if (IsCreativeAudioFormat(format)) {
        return IconGlyph::Bolt;
    }
    if (format == "html" || format == "json" || format == "md" || format == "jsx") {
        return IconGlyph::Documents;
    }
    return IconGlyph::Image;
}

ImVec4 ToastAccent(const std::string& tone)
{
    if (tone == "success") {
        return Rgba(38, 221, 123);
    }
    if (tone == "error") {
        return Rgba(248, 113, 113);
    }
    if (tone == "working") {
        return Rgba(205, 154, 82);
    }
    return Rgba(94, 150, 255);
}

IconGlyph ToastIcon(const std::string& title, const std::string& tone)
{
    if (tone == "error") {
        return IconGlyph::Bolt;
    }
    const std::string lowered = Lower(title);
    if (lowered.find("creative") != std::string::npos) {
        return IconGlyph::Image;
    }
    if (lowered.find("model") != std::string::npos || lowered.find("backend") != std::string::npos) {
        return IconGlyph::Globe;
    }
    if (lowered.find("settings") != std::string::npos) {
        return IconGlyph::Sliders;
    }
    if (lowered.find("validation") != std::string::npos) {
        return IconGlyph::Code;
    }
    return IconGlyph::Shield;
}

using GlyphRows = std::array<uint16_t, 16>;

const GlyphRows& Glyph(IconGlyph icon)
{
    static const GlyphRows shield = {
        0b0000011111100000,
        0b0001111111111000,
        0b0011100000011100,
        0b0111000000001110,
        0b0110001100010110,
        0b0110011110110110,
        0b0110011111100110,
        0b0110001111000110,
        0b0111001110001110,
        0b0011100100011100,
        0b0001110000111000,
        0b0000111001110000,
        0b0000011111100000,
        0b0000001111000000,
        0b0000000110000000,
        0b0000000000000000,
    };
    static const GlyphRows plus = {
        0b0000000000000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0001111111111000,
        0b0001111111111000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000110000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows chat = {
        0b0000000000000000,
        0b0001111111110000,
        0b0011000000011000,
        0b0110000000001100,
        0b0110011111001100,
        0b0110000000001100,
        0b0110011110001100,
        0b0110000000001100,
        0b0011000000011000,
        0b0001111111110000,
        0b0000011000000000,
        0b0000001100000000,
        0b0000000110000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows explore = {
        0b0000001111000000,
        0b0000111111110000,
        0b0001100000011000,
        0b0011000110001100,
        0b0011001111001100,
        0b0110011111100110,
        0b0110011001100110,
        0b0110000110000110,
        0b0011001111001100,
        0b0011000110001100,
        0b0001100000011000,
        0b0000111111110000,
        0b0000001111000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows agents = {
        0b0000000110000000,
        0b0000011111100000,
        0b0000110000110000,
        0b0000110110110000,
        0b0000110000110000,
        0b0000011111100000,
        0b0000000110000000,
        0b0011111111111100,
        0b0110000110000110,
        0b1100000110000011,
        0b0000011111100000,
        0b0000110000110000,
        0b0001100000011000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows documents = {
        0b0001111111100000,
        0b0001000000110000,
        0b0001000000011000,
        0b0001000000001000,
        0b0001011111001000,
        0b0001000000001000,
        0b0001011110001000,
        0b0001000000001000,
        0b0001011111001000,
        0b0001000000001000,
        0b0001000000001000,
        0b0001111111111000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows tools = {
        0b0001100000001100,
        0b0001110000011100,
        0b0000111000111000,
        0b0000011101110000,
        0b0000001111100000,
        0b0000000111000000,
        0b0000001111100000,
        0b0000011101110000,
        0b0000111000111000,
        0b0001110000011100,
        0b0011100000001110,
        0b0111000000000111,
        0b0110000000000011,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows history = {
        0b0000001111000000,
        0b0000111111110000,
        0b0001100000011000,
        0b0011000000001100,
        0b0110000110000110,
        0b0110000110000110,
        0b0110000111100110,
        0b0110000000100110,
        0b0011000000001100,
        0b0001100000011000,
        0b0000111111110000,
        0b0000001111000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows search = {
        0b0000001111000000,
        0b0000111111110000,
        0b0001100000011000,
        0b0011000000001100,
        0b0011000000001100,
        0b0011000000001100,
        0b0001100000011000,
        0b0000111111110000,
        0b0000001111000000,
        0b0000000011100000,
        0b0000000001110000,
        0b0000000000111000,
        0b0000000000011000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows globe = {
        0b0000001111000000,
        0b0000111111110000,
        0b0001100110011000,
        0b0011000110001100,
        0b0110000110000110,
        0b0111111111111110,
        0b0110000110000110,
        0b0110000110000110,
        0b0111111111111110,
        0b0011000110001100,
        0b0001100110011000,
        0b0000111111110000,
        0b0000001111000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows code = {
        0b0000000000000000,
        0b0000000011000000,
        0b0000000110000000,
        0b0000001100000000,
        0b0011001000011000,
        0b0110010000001100,
        0b1100100000000110,
        0b0110010000001100,
        0b0011001000011000,
        0b0000001100000000,
        0b0000011000000000,
        0b0000110000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows image = {
        0b0001111111111000,
        0b0011000000001100,
        0b0110000110000110,
        0b0110001111000110,
        0b0110000110000110,
        0b0110000000000110,
        0b0110000011000110,
        0b0110000111100110,
        0b0110001111110110,
        0b0110011110111110,
        0b0110111100011110,
        0b0011000000001100,
        0b0001111111111000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows sparkle = {
        0b0000000100000000,
        0b0000001110000000,
        0b0000011111000000,
        0b0000001110000000,
        0b0001101110110000,
        0b0011111111111000,
        0b0001101110110000,
        0b0000001110000000,
        0b0000011111000000,
        0b0000001110000000,
        0b0000000100000000,
        0b0011000000011000,
        0b0011000000011000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows attach = {
        0b0000000111100000,
        0b0000001100110000,
        0b0000011000011000,
        0b0000110000001100,
        0b0001100011000110,
        0b0011000111100011,
        0b0011001100110011,
        0b0001101100110110,
        0b0000110111101100,
        0b0000011000011000,
        0b0000001100110000,
        0b0000000111100000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows sliders = {
        0b0000100000001000,
        0b0000100000001000,
        0b0111111001111110,
        0b0000100000001000,
        0b0000000000000000,
        0b0010000000100000,
        0b0010000000100000,
        0b1111110011111100,
        0b0010000000100000,
        0b0000000000000000,
        0b0000010001000000,
        0b0000010001000000,
        0b0011111111110000,
        0b0000010001000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows send = {
        0b0000000000000000,
        0b0011111110000000,
        0b0000111111100000,
        0b0000001111111000,
        0b0000000011111110,
        0b0000000001111111,
        0b0000000011111110,
        0b0000001111111000,
        0b0000111111100000,
        0b0011111110000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows copy = {
        0b0000011111110000,
        0b0000010000010000,
        0b0000010000010000,
        0b0011111110010000,
        0b0010000010010000,
        0b0010000011110000,
        0b0010000010000000,
        0b0010000010000000,
        0b0010000010000000,
        0b0011111110000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows like = {
        0b0000000110000000,
        0b0000001110000000,
        0b0000011110000000,
        0b0000111100000000,
        0b0111111111110000,
        0b1100000010011000,
        0b1100000010011000,
        0b1100000010011000,
        0b0111111111110000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows dislike = {
        0b0111111111110000,
        0b1100000010011000,
        0b1100000010011000,
        0b1100000010011000,
        0b0111111111110000,
        0b0000111100000000,
        0b0000011110000000,
        0b0000001110000000,
        0b0000000110000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows regen = {
        0b0000011111000000,
        0b0001110001110000,
        0b0011000000011000,
        0b0110000000001100,
        0b0110000001111100,
        0b0110000000011000,
        0b0011000000110000,
        0b0001110001110000,
        0b0000011111000000,
        0b0011111000000000,
        0b0001100000000000,
        0b0000110000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows chevron = {
        0b0000000000000000,
        0b0000011000000000,
        0b0000001100000000,
        0b0000000110000000,
        0b0000000011000000,
        0b0000000001100000,
        0b0000000011000000,
        0b0000000110000000,
        0b0000001100000000,
        0b0000011000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows mail = {
        0b0001111111111000,
        0b0011000000001100,
        0b0110110000110110,
        0b0110011001100110,
        0b0110001111000110,
        0b0110000110000110,
        0b0110000000000110,
        0b0110000000000110,
        0b0011000000001100,
        0b0001111111111000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };
    static const GlyphRows bolt = {
        0b0000000011000000,
        0b0000000110000000,
        0b0000001100000000,
        0b0000011111100000,
        0b0000001110000000,
        0b0000011100000000,
        0b0000110000000000,
        0b0001100000000000,
        0b0011111110000000,
        0b0000011000000000,
        0b0000110000000000,
        0b0001100000000000,
        0b0001000000000000,
        0b0000000000000000,
        0b0000000000000000,
        0b0000000000000000,
    };

    switch (icon) {
    case IconGlyph::Shield: return shield;
    case IconGlyph::Plus: return plus;
    case IconGlyph::Chat: return chat;
    case IconGlyph::Explore: return explore;
    case IconGlyph::Agents: return agents;
    case IconGlyph::Documents: return documents;
    case IconGlyph::Tools: return tools;
    case IconGlyph::History: return history;
    case IconGlyph::Search: return search;
    case IconGlyph::Globe: return globe;
    case IconGlyph::Code: return code;
    case IconGlyph::Document: return documents;
    case IconGlyph::Image: return image;
    case IconGlyph::Sparkle: return sparkle;
    case IconGlyph::Attach: return attach;
    case IconGlyph::Sliders: return sliders;
    case IconGlyph::Send: return send;
    case IconGlyph::Copy: return copy;
    case IconGlyph::Like: return like;
    case IconGlyph::Dislike: return dislike;
    case IconGlyph::Regen: return regen;
    case IconGlyph::Chevron: return chevron;
    case IconGlyph::Mail: return mail;
    case IconGlyph::Bolt: return bolt;
    default: return chat;
    }
}

void DrawBitmapIcon(ImDrawList* draw, IconGlyph icon, ImVec2 pos, float size, ImU32 color)
{
    const GlyphRows& rows = Glyph(icon);
    const float cell = size / 16.0f;
    const float pad = std::max(0.0f, cell * 0.08f);
    for (int y = 0; y < 16; ++y) {
        const uint16_t row = rows[static_cast<size_t>(y)];
        for (int x = 0; x < 16; ++x) {
            if ((row & (1u << (15 - x))) == 0) {
                continue;
            }
            const ImVec2 a(pos.x + x * cell + pad, pos.y + y * cell + pad);
            const ImVec2 b(pos.x + (x + 1) * cell - pad, pos.y + (y + 1) * cell - pad);
            draw->AddRectFilled(a, b, color, cell * 0.2f);
        }
    }
}

void TextColor(const char* text, ImVec4 color)
{
    ImGui::PushStyleColor(ImGuiCol_Text, color);
    ImGui::TextUnformatted(text);
    ImGui::PopStyleColor();
}

void TextColor(const std::string& text, ImVec4 color)
{
    TextColor(text.c_str(), color);
}

void DrawSoftPanel(ImVec2 min, ImVec2 max, float rounding = 12.0f, bool accent = false)
{
    ImDrawList* draw = ImGui::GetWindowDrawList();
    draw->AddRectFilled(min, max, Color(13, 19, 26, 0.94f), rounding);
    draw->AddRect(min, max, accent ? Color(38, 221, 123, 0.90f) : Color(44, 54, 65, 0.78f), rounding, 0, accent ? 1.5f : 1.0f);
}

void DrawPremiumBackground(ImDrawList* draw, ImVec2 min, ImVec2 max, float reveal = 1.0f)
{
    const float width = max.x - min.x;
    const float t = static_cast<float>(ImGui::GetTime());
    const float alpha = Clamp01(reveal);

    draw->AddRectFilled(min, max, Color(3, 7, 12), 0.0f);
    draw->AddRectFilledMultiColor(
        min,
        max,
        Color(3, 8, 13, 1.0f * alpha),
        Color(6, 10, 17, 1.0f * alpha),
        Color(3, 6, 11, 1.0f * alpha),
        Color(3, 8, 12, 1.0f * alpha));

    const float grid_alpha = 0.010f * alpha;
    const float x_offset = std::fmod(t * 4.0f, 96.0f);
    const float y_offset = std::fmod(t * 3.0f, 88.0f);
    for (float x = min.x - 96.0f + x_offset; x < max.x + 96.0f; x += 96.0f) {
        draw->AddLine(ImVec2(x, min.y), ImVec2(x, max.y), Color(190, 220, 205, grid_alpha), 1.0f);
    }
    for (float y = min.y - 88.0f + y_offset; y < max.y + 88.0f; y += 88.0f) {
        draw->AddLine(ImVec2(min.x, y), ImVec2(max.x, y), Color(190, 220, 205, grid_alpha * 0.78f), 1.0f);
    }

    const float sweep = std::fmod(t * 0.10f, 1.0f);
    const float sweep_x = min.x + width * sweep;
    draw->AddRectFilledMultiColor(
        ImVec2(sweep_x - 120.0f, min.y),
        ImVec2(sweep_x + 120.0f, max.y),
        Color(255, 255, 255, 0.0f),
        Color(255, 255, 255, 0.012f * alpha),
        Color(255, 255, 255, 0.010f * alpha),
        Color(255, 255, 255, 0.0f));

    draw->AddRectFilledMultiColor(
        min,
        ImVec2(max.x, min.y + 148.0f),
        Color(255, 255, 255, 0.052f * alpha),
        Color(255, 255, 255, 0.018f * alpha),
        Color(255, 255, 255, 0.0f),
        Color(255, 255, 255, 0.0f));
    draw->AddLine(ImVec2(min.x, min.y + 1.0f), ImVec2(max.x, min.y + 1.0f), Color(255, 255, 255, 0.10f * alpha), 1.0f);
    draw->AddLine(ImVec2(min.x, max.y - 1.0f), ImVec2(max.x, max.y - 1.0f), Color(0, 0, 0, 0.50f * alpha), 1.0f);
}

void DrawSpinner(ImDrawList* draw, ImVec2 center, float radius, float thickness, ImU32 track, ImU32 accent)
{
    constexpr float two_pi = 6.28318530718f;
    const float t = static_cast<float>(ImGui::GetTime());
    draw->PathClear();
    for (int i = 0; i <= 64; ++i) {
        const float a = two_pi * static_cast<float>(i) / 64.0f;
        draw->PathLineTo(ImVec2(center.x + std::cos(a) * radius, center.y + std::sin(a) * radius));
    }
    draw->PathStroke(track, false, thickness);

    const float start = t * 2.8f;
    const float span = 1.18f + Pulse(2.2f) * 0.42f;
    draw->PathClear();
    for (int i = 0; i <= 36; ++i) {
        const float a = start + span * static_cast<float>(i) / 36.0f;
        draw->PathLineTo(ImVec2(center.x + std::cos(a) * radius, center.y + std::sin(a) * radius));
    }
    draw->PathStroke(accent, false, thickness);
}

bool BeginCard(const char* id, ImVec2 size, bool accent = false)
{
    ImVec2 draw_size = size;
    const ImVec2 avail = ImGui::GetContentRegionAvail();
    if (draw_size.x <= 0.0f) {
        draw_size.x = avail.x;
    }
    if (draw_size.y <= 0.0f) {
        draw_size.y = avail.y;
    }

    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const ImVec2 max(pos.x + draw_size.x, pos.y + draw_size.y);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const bool composer = std::strstr(id, "composer") != nullptr;
    draw->AddRectFilled(ImVec2(pos.x, pos.y + 5.0f), ImVec2(max.x, max.y + 8.0f), Color(0, 0, 0, accent ? 0.18f : 0.16f), 14.0f);
    draw->AddRectFilledMultiColor(
        pos,
        max,
        Color(14, 20, 28, 0.94f),
        Color(13, 19, 27, 0.94f),
        Color(9, 13, 20, 0.97f),
        Color(9, 15, 22, 0.97f));
    draw->AddRect(pos, max, composer ? Color(38, 221, 123, 0.76f) : Color(57, 68, 82, accent ? 0.64f : 0.58f), 14.0f, 0, composer ? 1.35f : 1.0f);
    draw->AddLine(ImVec2(pos.x + 14.0f, pos.y + 1.0f), ImVec2(max.x - 14.0f, pos.y + 1.0f), Color(255, 255, 255, accent ? 0.08f : 0.06f), 1.0f);

    ImGui::PushStyleVar(ImGuiStyleVar_ChildRounding, 14.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_ChildBorderSize, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(16.0f, 14.0f));
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(0, 0, 0, 0));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(0, 0, 0, 0));
    const bool open = ImGui::BeginChild(id, size, false);
    ImGui::PopStyleColor(2);
    ImGui::PopStyleVar(3);
    return open;
}

void EndCard()
{
    ImGui::EndChild();
}

bool IconTextButton(const char* id, IconGlyph icon, const char* label, ImVec2 size, ImVec4 bg, ImVec4 hover, ImVec4 text_color)
{
    if (size.x <= 0.0f) {
        size.x = ImGui::GetContentRegionAvail().x;
    }
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const bool clicked = ImGui::InvisibleButton(id, size);
    const bool hovered = ImGui::IsItemHovered();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 max(pos.x + size.x, pos.y + size.y);
    const bool primary = bg.y > bg.x && bg.y > bg.z && bg.y > 0.45f;
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    draw->AddRectFilled(ImVec2(pos.x, pos.y + (hovered ? 3.0f : 4.0f)), ImVec2(max.x, max.y + 4.0f), Color(0, 0, 0, hovered ? 0.22f : 0.14f), 8.0f);
    draw->AddRectFilled(pos, max, ImGui::GetColorU32(hovered ? hover : bg), 8.0f);
    draw->AddRect(pos, max, primary ? Color(164, 255, 198, hovered ? 0.28f : 0.13f) : Color(255, 255, 255, hovered ? 0.13f : 0.055f), 8.0f, 0, 1.0f);
    if (primary || hovered) {
        const float shimmer = std::fmod(static_cast<float>(ImGui::GetTime()) * 0.9f, 1.0f);
        const float x = pos.x + (size.x + 70.0f) * shimmer - 70.0f;
        draw->PushClipRect(pos, max, true);
        draw->AddRectFilledMultiColor(
            ImVec2(x, pos.y),
            ImVec2(x + 70.0f, max.y),
            Color(255, 255, 255, 0.0f),
            Color(255, 255, 255, hovered ? 0.12f : 0.07f),
            Color(255, 255, 255, hovered ? 0.10f : 0.05f),
            Color(255, 255, 255, 0.0f));
        draw->PopClipRect();
    }
    DrawBitmapIcon(draw, icon, ImVec2(pos.x + 15.0f, pos.y + (size.y - 16.0f) * 0.5f), 16.0f, ImGui::GetColorU32(text_color));
    draw->AddText(ImVec2(pos.x + 42.0f, pos.y + (size.y - ImGui::GetFontSize()) * 0.5f - 1.0f), ImGui::GetColorU32(text_color), label);
    return clicked;
}

bool IconOnlyButton(const char* id, IconGlyph icon, ImVec2 size, ImVec4 bg, ImVec4 hover, ImVec4 icon_color)
{
    if (size.x <= 0.0f) {
        size.x = ImGui::GetContentRegionAvail().x;
    }
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const bool clicked = ImGui::InvisibleButton(id, size);
    const bool hovered = ImGui::IsItemHovered();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 max(pos.x + size.x, pos.y + size.y);
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    draw->AddRectFilled(ImVec2(pos.x, pos.y + (hovered ? 2.0f : 3.0f)), ImVec2(max.x, max.y + 3.0f), Color(0, 0, 0, hovered ? 0.18f : 0.10f), 8.0f);
    draw->AddRectFilled(pos, max, ImGui::GetColorU32(hovered ? hover : bg), 8.0f);
    draw->AddRect(pos, max, Color(255, 255, 255, hovered ? 0.12f : 0.045f), 8.0f);
    const float icon_size = std::min(size.x, size.y) * 0.45f;
    DrawBitmapIcon(draw, icon, ImVec2(pos.x + (size.x - icon_size) * 0.5f, pos.y + (size.y - icon_size) * 0.5f), icon_size, ImGui::GetColorU32(icon_color));
    return clicked;
}

bool ChromeButton(const char* id, const char* symbol, ImVec2 pos, ImVec2 size, ImVec4 hover, ImVec4 active, ImVec4 text_color)
{
    (void)id;
    ImGuiIO& io = ImGui::GetIO();
    const bool hovered =
        io.MousePos.x >= pos.x && io.MousePos.x <= pos.x + size.x &&
        io.MousePos.y >= pos.y && io.MousePos.y <= pos.y + size.y;
    const bool clicked = hovered && ImGui::IsMouseClicked(ImGuiMouseButton_Left);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    if (hovered) {
        draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), ImGui::GetColorU32(active), 6.0f);
    } else {
        draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), ImGui::GetColorU32(hover), 6.0f);
    }
    const ImVec2 text_size = ImGui::CalcTextSize(symbol);
    draw->AddText(
        ImVec2(pos.x + (size.x - text_size.x) * 0.5f, pos.y + (size.y - text_size.y) * 0.5f - 1.0f),
        ImGui::GetColorU32(text_color),
        symbol);
    return clicked;
}

void DrawWindowControls()
{
    const ImVec2 origin = ImGui::GetWindowPos();
    const ImVec2 window_size = ImGui::GetWindowSize();
    const float top = origin.y + 8.0f;
    const float right = origin.x + window_size.x - 10.0f;
    const ImVec2 button_size(34.0f, 28.0f);

    if (ChromeButton("chrome_minimize", "-", ImVec2(right - 112.0f, top), button_size, Rgba(0, 0, 0, 0.0f), Rgba(30, 39, 49, 0.95f), Rgba(215, 222, 231))) {
        RequestWindowMinimize();
    }
    if (ChromeButton("chrome_maximize", "[]", ImVec2(right - 74.0f, top), button_size, Rgba(0, 0, 0, 0.0f), Rgba(30, 39, 49, 0.95f), Rgba(215, 222, 231))) {
        RequestWindowMaximizeRestore();
    }
    if (ChromeButton("chrome_close", "X", ImVec2(right - 36.0f, top), button_size, Rgba(0, 0, 0, 0.0f), Rgba(190, 42, 58, 0.95f), Rgba(255, 255, 255))) {
        RequestWindowClose();
    }
}

bool NavButton(const char* id, IconGlyph icon, const char* label, bool selected)
{
    const float width = ImGui::GetContentRegionAvail().x;
    const ImVec2 size(width, 40.0f);
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const bool clicked = ImGui::InvisibleButton(id, size);
    const bool hovered = ImGui::IsItemHovered();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    const ImU32 bg = selected ? Color(13, 63, 44, 0.78f) : (hovered ? Color(25, 35, 45, 0.92f) : Color(0, 0, 0, 0));
    draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), bg, 7.0f);
    if (selected) {
        const float pulse = 0.72f + Pulse(2.8f) * 0.28f;
        draw->AddRectFilled(ImVec2(pos.x, pos.y + 7.0f), ImVec2(pos.x + 3.0f, pos.y + size.y - 7.0f), Color(38, 221, 123, pulse), 2.0f);
        draw->AddRect(pos, ImVec2(pos.x + size.x, pos.y + size.y), Color(255, 255, 255, 0.055f), 7.0f);
    }
    const ImVec4 color = selected ? Rgba(38, 221, 123) : Rgba(198, 205, 213);
    DrawBitmapIcon(draw, icon, ImVec2(pos.x + 14.0f, pos.y + 12.0f), 16.0f, ImGui::GetColorU32(color));
    draw->AddText(ImVec2(pos.x + 40.0f, pos.y + 11.0f), ImGui::GetColorU32(color), label);
    return clicked;
}

bool RowButton(const char* id, IconGlyph icon, const char* title, const char* subtitle, bool active = false)
{
    const float width = ImGui::GetContentRegionAvail().x;
    const ImVec2 size(width, subtitle == nullptr || subtitle[0] == '\0' ? 38.0f : 48.0f);
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const bool clicked = ImGui::InvisibleButton(id, size);
    const bool hovered = ImGui::IsItemHovered();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    const ImU32 row_bg = active ? Color(15, 69, 47, 0.78f) : (hovered ? Color(25, 34, 44, 0.92f) : Color(0, 0, 0, 0));
    draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), row_bg, 8.0f);
    if (hovered || active) {
        draw->AddRect(pos, ImVec2(pos.x + size.x, pos.y + size.y), active ? Color(255, 255, 255, 0.055f) : Color(255, 255, 255, 0.075f), 8.0f);
    }
    if (active) {
        draw->AddRectFilled(ImVec2(pos.x, pos.y + 8.0f), ImVec2(pos.x + 3.0f, pos.y + size.y - 8.0f), Color(38, 221, 123), 2.0f);
    }

    const ImVec2 icon_box(pos.x + 10.0f, pos.y + 7.0f);
    draw->AddRectFilled(icon_box, ImVec2(icon_box.x + 34.0f, icon_box.y + 34.0f), Color(21, 29, 39, 0.95f), 7.0f);
    DrawBitmapIcon(draw, icon, ImVec2(icon_box.x + 9.0f, icon_box.y + 9.0f), 16.0f, active ? Color(38, 221, 123) : Color(215, 222, 230));
    draw->AddText(ImVec2(pos.x + 54.0f, pos.y + 8.0f), active ? Color(38, 221, 123) : Color(238, 242, 246), title);
    if (subtitle != nullptr && subtitle[0] != '\0') {
        draw->AddText(ImVec2(pos.x + 54.0f, pos.y + 27.0f), Color(139, 149, 160), subtitle);
    }
    DrawBitmapIcon(draw, IconGlyph::Chevron, ImVec2(pos.x + size.x - 22.0f, pos.y + (size.y - 14.0f) * 0.5f), 14.0f, Color(151, 160, 171));
    return clicked;
}

void DrawProgress(float fraction, ImVec2 size, bool animated = false)
{
    fraction = std::max(0.0f, std::min(1.0f, fraction));
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 max(pos.x + size.x, pos.y + size.y);
    const ImVec2 fill_max(pos.x + size.x * fraction, pos.y + size.y);
    draw->AddRectFilled(pos, max, Color(24, 32, 42), size.y * 0.5f);
    draw->AddRectFilledMultiColor(pos, fill_max, Color(30, 176, 99), Color(74, 222, 128), Color(38, 221, 123), Color(15, 118, 89));
    draw->AddRect(pos, max, Color(255, 255, 255, 0.065f), size.y * 0.5f);
    if (animated && fraction > 0.04f) {
        const float shimmer = std::fmod(static_cast<float>(ImGui::GetTime()) * 0.85f, 1.0f);
        const float x = pos.x + std::max(0.0f, size.x * fraction - 80.0f) * shimmer;
        draw->PushClipRect(pos, fill_max, true);
        draw->AddRectFilledMultiColor(
            ImVec2(x, pos.y),
            ImVec2(x + 80.0f, pos.y + size.y),
            Color(255, 255, 255, 0.0f),
            Color(255, 255, 255, 0.24f),
            Color(255, 255, 255, 0.18f),
            Color(255, 255, 255, 0.0f));
        draw->PopClipRect();
    }
    ImGui::Dummy(size);
}

std::string LatestUserPrompt(const std::vector<ChatMessage>& history)
{
    for (auto it = history.rbegin(); it != history.rend(); ++it) {
        if (it->role == "user") {
            return it->content;
        }
    }
    return "Analyze the current project and give me the highest-impact next steps.";
}

int ApproxTokensFromChars(size_t chars)
{
    if (chars == 0) {
        return 0;
    }
    return static_cast<int>(std::max<size_t>(1, (chars + 3) / 4));
}

int ApproxTokens(const std::vector<ChatMessage>& history)
{
    size_t chars = 0;
    for (const ChatMessage& item : history) {
        chars += item.content.size();
    }
    return ApproxTokensFromChars(chars);
}

std::string FormatModelBytes(long long bytes)
{
    if (bytes <= 0) {
        return "-";
    }
    const char* units[] = {"B", "KB", "MB", "GB", "TB"};
    double value = static_cast<double>(bytes);
    int unit = 0;
    while (value >= 1024.0 && unit < 4) {
        value /= 1024.0;
        ++unit;
    }
    std::ostringstream stream;
    stream.setf(std::ios::fixed);
    stream.precision(unit == 0 ? 0 : 1);
    stream << value << " " << units[unit];
    return stream.str();
}

std::string CapabilitySummary(const ModelCapabilities& capabilities)
{
    std::vector<std::string> labels;
    if (capabilities.chat) {
        labels.push_back("chat");
    }
    if (capabilities.streaming) {
        labels.push_back("stream");
    }
    if (capabilities.structured_json) {
        labels.push_back("json");
    }
    if (capabilities.tools) {
        labels.push_back("tools");
    }
    if (capabilities.vision) {
        labels.push_back("vision");
    }
    if (capabilities.audio) {
        labels.push_back("audio");
    }
    if (capabilities.embeddings) {
        labels.push_back("embed");
    }
    if (capabilities.computer_use) {
        labels.push_back("computer");
    }
    if (labels.empty()) {
        return "unknown";
    }

    std::ostringstream stream;
    for (size_t i = 0; i < labels.size(); ++i) {
        if (i > 0) {
            stream << " / ";
        }
        stream << labels[i];
    }
    return stream.str();
}

std::filesystem::path ConversationSnapshotPath()
{
    return AppDataDirectory() / "conversation_last.json";
}

std::filesystem::path ConversationLibraryDirectory()
{
    return AppDataDirectory() / "conversations";
}

std::string TimestampForFileName()
{
    const auto now = std::chrono::system_clock::now();
    const std::time_t tt = std::chrono::system_clock::to_time_t(now);
    std::tm local{};
    localtime_s(&local, &tt);
    std::ostringstream stream;
    stream << std::put_time(&local, "%Y%m%d-%H%M%S");
    return stream.str();
}

std::string NewConversationId()
{
    const auto now = std::chrono::system_clock::now();
    const auto millis = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count() % 1000;
    std::ostringstream stream;
    stream << TimestampForFileName() << "-" << std::setw(3) << std::setfill('0') << millis;
    return stream.str();
}

std::filesystem::path ConversationLibraryPath(const std::string& id)
{
    const std::string safe_id = Trim(id).empty() ? NewConversationId() : Trim(id);
    return ConversationLibraryDirectory() / (safe_id + ".json");
}

std::filesystem::path ConversationExportPath()
{
    return AppDataDirectory() / "exports" / ("AegisChat-" + TimestampForFileName() + ".md");
}

std::filesystem::path PatchExportPath()
{
    return AppDataDirectory() / "exports" / ("AegisPatch-" + TimestampForFileName() + ".patch");
}

std::filesystem::path CreativeExportDirectory()
{
    return AppDataDirectory() / "exports" / "creative";
}

std::string SafeExportSegment(const std::string& value, const std::string& fallback)
{
    std::string out;
    for (const unsigned char ch : Trim(value)) {
        if (std::isalnum(ch) || ch == '-' || ch == '_' || ch == '.') {
            out.push_back(static_cast<char>(ch));
        } else if (ch == ' ' || ch == ':' || ch == '/' || ch == '\\') {
            out.push_back('-');
        }
    }
    while (out.find("--") != std::string::npos) {
        out.replace(out.find("--"), 2, "-");
    }
    while (!out.empty() && (out.front() == '-' || out.front() == '.')) {
        out.erase(out.begin());
    }
    while (!out.empty() && (out.back() == '-' || out.back() == '.')) {
        out.pop_back();
    }
    if (out.empty()) {
        out = fallback;
    }
    return Shorten(out, 80);
}

std::filesystem::path CreativeJobExportPath(const MediaJobSummary& job)
{
    const std::string kind = SafeExportSegment(job.kind, "creative");
    const std::string id = SafeExportSegment(job.id, "job");
    return CreativeExportDirectory() / ("AegisCreative-" + kind + "-" + id + "-" + TimestampForFileName());
}

std::filesystem::path CreativeAssetExportPath(const MediaAssetInfo& asset, const std::string& job_id)
{
    const std::filesystem::path source(Utf8ToWide(asset.path));
    std::filesystem::path file_name = source.filename();
    if (file_name.empty()) {
        std::string generated = "asset-" + TimestampForFileName();
        const std::string format = SafeExportSegment(asset.format, "");
        if (!format.empty()) {
            generated += "." + format;
        }
        file_name = std::filesystem::path(Utf8ToWide(generated));
    }
    return CreativeExportDirectory() / (SafeExportSegment(job_id, "job") + "-" + TimestampForFileName()) / file_name;
}

std::string JsonQuoted(const std::string& value)
{
    return "\"" + EscapeJson(value) + "\"";
}

std::string ConversationTitleFromHistory(const std::vector<ChatMessage>& history)
{
    for (const ChatMessage& message : history) {
        if (message.role == "user" && !Trim(message.content).empty()) {
            return Shorten(Trim(message.content), 72);
        }
    }
    for (const ChatMessage& message : history) {
        if (!Trim(message.content).empty()) {
            return Shorten(Trim(message.content), 72);
        }
    }
    return "New Aegis Chat";
}

std::string ConversationPreviewFromHistory(const std::vector<ChatMessage>& history)
{
    for (auto it = history.rbegin(); it != history.rend(); ++it) {
        if (!Trim(it->content).empty()) {
            return Shorten(Trim(it->content), 120);
        }
    }
    return "No messages yet.";
}

std::vector<ChatMessage> ParseConversationMessages(const JsonValue& value)
{
    std::vector<ChatMessage> messages;
    if (!value.IsArray()) {
        return messages;
    }
    messages.reserve(value.array_value.size());
    for (const JsonValue& item : value.array_value) {
        if (!item.IsObject()) {
            continue;
        }
        ChatMessage message;
        message.role = item["role"].AsString();
        message.content = item["content"].AsString();
        message.time_label = item["time_label"].AsString();
        message.model_label = item["model_label"].AsString();
        if (!Trim(message.role).empty() && !Trim(message.content).empty()) {
            messages.push_back(std::move(message));
        }
    }
    return messages;
}

long long FileSortKey(const std::filesystem::path& path)
{
    std::error_code ec;
    const auto time = std::filesystem::last_write_time(path, ec);
    if (ec) {
        return 0;
    }
    return static_cast<long long>(time.time_since_epoch().count());
}

void WriteConversationFile(
    const std::filesystem::path& path,
    const std::string& id,
    const std::string& title,
    bool pinned,
    bool archived,
    const std::vector<ChatMessage>& history,
    const std::string& workspace_root,
    const std::string& active_model)
{
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
        return;
    }

    const size_t max_messages = 200;
    const size_t start = history.size() > max_messages ? history.size() - max_messages : 0;
    file << "{\n";
    file << "  \"version\":2,\n";
    file << "  \"id\":" << JsonQuoted(id) << ",\n";
    file << "  \"title\":" << JsonQuoted(title.empty() ? ConversationTitleFromHistory(history) : title) << ",\n";
    file << "  \"preview\":" << JsonQuoted(ConversationPreviewFromHistory(history)) << ",\n";
    file << "  \"saved_at\":" << JsonQuoted(NowTimeLabel()) << ",\n";
    file << "  \"pinned\":" << (pinned ? "true" : "false") << ",\n";
    file << "  \"archived\":" << (archived ? "true" : "false") << ",\n";
    file << "  \"workspace_root\":" << JsonQuoted(workspace_root) << ",\n";
    file << "  \"active_model\":" << JsonQuoted(active_model) << ",\n";
    file << "  \"messages\":[\n";
    bool first = true;
    for (size_t i = start; i < history.size(); ++i) {
        const ChatMessage& message = history[i];
        if (Trim(message.role).empty() || Trim(message.content).empty()) {
            continue;
        }
        if (!first) {
            file << ",\n";
        }
        first = false;
        file << "    {";
        file << "\"role\":" << JsonQuoted(message.role) << ",";
        file << "\"content\":" << JsonQuoted(message.content) << ",";
        file << "\"time_label\":" << JsonQuoted(message.time_label) << ",";
        file << "\"model_label\":" << JsonQuoted(message.model_label);
        file << "}";
    }
    file << "\n  ]\n";
    file << "}\n";
}

bool LoadConversationFilePayload(
    const std::filesystem::path& path,
    JsonValue* out,
    std::vector<ChatMessage>* messages)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        return false;
    }
    const std::string body((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok || !parsed.value.IsObject()) {
        return false;
    }
    if (out != nullptr) {
        *out = parsed.value;
    }
    if (messages != nullptr) {
        *messages = ParseConversationMessages(parsed.value["messages"]);
    }
    return true;
}

std::string AttachmentSummary(const std::vector<FileContent>& attachments)
{
    if (attachments.empty()) {
        return {};
    }

    std::ostringstream summary;
    summary << "Attachments:";
    for (const FileContent& attachment : attachments) {
        summary << "\n- " << attachment.path;
    }
    return summary.str();
}

std::string BuildMessageWithAttachments(const std::string& message, const std::vector<FileContent>& attachments)
{
    std::ostringstream body;
    body << (Trim(message).empty() ? "Use the attached workspace file(s) as context." : message);
    if (attachments.empty()) {
        return body.str();
    }

    body << "\n\nAttached workspace file context:";
    for (const FileContent& attachment : attachments) {
        std::string content = attachment.content;
        bool truncated = false;
        constexpr size_t max_attachment_chars = 7000;
        if (content.size() > max_attachment_chars) {
            content = content.substr(0, max_attachment_chars);
            truncated = true;
        }

        body << "\n\n--- " << attachment.path << " ---\n";
        body << content;
        if (truncated) {
            body << "\n...[attachment truncated by desktop client]";
        }
    }
    return body.str();
}

bool IsLoopbackEndpoint(const std::string& endpoint)
{
    const std::string lowered = Lower(Trim(endpoint));
    return lowered.empty() ||
        lowered.find("127.0.0.1") != std::string::npos ||
        lowered.find("localhost") != std::string::npos ||
        lowered.find("[::1]") != std::string::npos ||
        lowered.find("://::1") != std::string::npos ||
        lowered.find("0.0.0.0") != std::string::npos;
}

bool IsCloudModelTarget(const std::string& api, const std::string& endpoint)
{
    const std::string lowered_api = Lower(Trim(api));
    const std::string lowered_endpoint = Lower(Trim(endpoint));
    if (IsLoopbackEndpoint(lowered_endpoint)) {
        return false;
    }

    if (lowered_api.empty() ||
        lowered_api == "ollama" ||
        lowered_api == "local" ||
        lowered_api == "llama.cpp" ||
        lowered_api == "llamacpp" ||
        lowered_api == "lmstudio") {
        return lowered_endpoint.rfind("https://", 0) == 0;
    }

    return true;
}

}

AegisChatApp::AegisChatApp()
    : settings_(LoadDesktopSettings()),
      client_(settings_)
{
    HydrateDesktopBuffers();
    SetBuffer(login_user_buffer_, "MercyTheGod");
    SetBuffer(media_aspect_ratio_buffer_, "16:9");
    SetBuffer(media_style_buffer_, "premium native desktop product");
    SetBuffer(media_output_formats_buffer_, "");
    login_status_.clear();
}

AegisChatApp::~AegisChatApp()
{
    if (active_task_.valid()) {
        active_task_.wait();
    }
    StopAudioPreview();
    ClearCreativeTextureCache();
}

void AegisChatApp::Initialize()
{
    LoadConversationSnapshot();

    const std::string smoke = Lower(Trim(GetEnvUtf8(L"AEGIS_CHATBOT_SMOKE_AUTO_LOGIN")));
    smoke_auto_login_ = smoke == "1" || smoke == "true" || smoke == "yes" || smoke == "on";
    if (smoke_auto_login_) {
        int delay_ms = 2400;
        const std::string delay_value = Trim(GetEnvUtf8(L"AEGIS_CHATBOT_SMOKE_AUTO_LOGIN_DELAY_MS"));
        if (!delay_value.empty()) {
            try {
                delay_ms = std::clamp(std::stoi(delay_value), 500, 10000);
            } catch (const std::exception&) {
                delay_ms = 2400;
            }
        }
        smoke_auto_login_at_ = std::chrono::steady_clock::now() + std::chrono::milliseconds(delay_ms);
        login_status_ = "Smoke test: auto-login queued.";
    }
}

void AegisChatApp::Tick()
{
    if (active_task_.valid() && active_task_.wait_for(std::chrono::milliseconds(0)) == std::future_status::ready) {
        Completion completion;
        try {
            completion = active_task_.get();
        } catch (const std::exception& error) {
            const std::string message = error.what();
            completion = [this, message]() { status_ = message; };
        }

        if (completion) {
            try {
                completion();
            } catch (const std::exception& error) {
                status_ = error.what();
            }
        }
        busy_ = false;
        busy_label_.clear();
    }

    const auto now = std::chrono::steady_clock::now();
    if (!authenticated_) {
        if (smoke_auto_login_ && !smoke_auto_login_done_ && now >= smoke_auto_login_at_) {
            smoke_auto_login_done_ = true;
            AttemptLogin(true);
        }
        return;
    }

    if (!dashboard_ready_) {
        if (setup_started_.time_since_epoch().count() == 0) {
            setup_started_ = now;
        }
        const auto elapsed = now - setup_started_;
        const bool minimum_elapsed = elapsed >= std::chrono::milliseconds(2800);
        const bool long_wait = elapsed >= std::chrono::milliseconds(6200);
        if (minimum_elapsed && (!busy_ || long_wait)) {
            dashboard_ready_ = true;
            dashboard_reveal_time_ = static_cast<float>(ImGui::GetTime());
            next_health_check_ = now + std::chrono::seconds(10);
            if (status_.empty() || status_ == "Preparing Aegis AI Chat...") {
                status_ = busy_ ? "Dashboard ready. Backend is still finishing setup." : "Dashboard ready.";
            }
            if (!setup_check_auto_opened_) {
                setup_check_auto_opened_ = true;
                const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
                std::error_code ec;
                const bool workspace_ready = !workspace.empty() &&
                    std::filesystem::exists(std::filesystem::path(Utf8ToWide(workspace)), ec) &&
                    std::filesystem::is_directory(std::filesystem::path(Utf8ToWide(workspace)), ec);
                if (!health_.engine_ready || !health_.model_ready || !workspace_ready || !has_config_) {
                    pending_popup_ = "Aegis Setup Check";
                }
            }
        }
        return;
    }

    if (!busy_ && now >= next_health_check_) {
        next_health_check_ = now + std::chrono::seconds(10);
        RefreshRuntime(false);
    }
}

void AegisChatApp::Render()
{
    ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImVec2 app_size = viewport->WorkSize;
    const auto host_size = HostWindowSize();
    if (host_size.first > 320.0f && host_size.second > 240.0f) {
        app_size = ImVec2(host_size.first, host_size.second);
    }
    ImGui::SetNextWindowPos(viewport->WorkPos);
    ImGui::SetNextWindowSize(app_size);

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove |
        ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoBringToFrontOnFocus;

    ImGui::Begin("Aegis ChatBot Desktop", nullptr, flags);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 min = ImGui::GetWindowPos();
    const ImVec2 max(min.x + ImGui::GetWindowSize().x, min.y + ImGui::GetWindowSize().y);
    const float dashboard_reveal = dashboard_ready_ && dashboard_reveal_time_ > 0.0f
        ? EaseOutCubic((static_cast<float>(ImGui::GetTime()) - dashboard_reveal_time_) / 0.55f)
        : 1.0f;
    DrawPremiumBackground(draw, min, max, dashboard_reveal);

    if (!authenticated_) {
        RenderLogin();
        SyncStatusToast();
        RenderToasts();
        DrawWindowControls();
        ImGui::End();
        return;
    }

    if (!dashboard_ready_) {
        RenderSetupLoading();
        SyncStatusToast();
        RenderToasts();
        DrawWindowControls();
        ImGui::End();
        return;
    }

    HandleKeyboardShortcuts();
    ImGui::PushStyleVar(ImGuiStyleVar_Alpha, dashboard_reveal);
    ImGui::SetCursorPos(ImVec2(0.0f, (1.0f - dashboard_reveal) * 18.0f));
    if (ImGui::BeginTable("app_shell", 2, ImGuiTableFlags_NoSavedSettings)) {
        ImGui::TableSetupColumn("Sidebar", ImGuiTableColumnFlags_WidthFixed, 276.0f);
        ImGui::TableSetupColumn("Workspace", ImGuiTableColumnFlags_WidthStretch, 1.0f);
        ImGui::TableNextRow();

        ImGui::TableSetColumnIndex(0);
        RenderLeftPanel();

        ImGui::TableSetColumnIndex(1);
        RenderTopBar();
        ImGui::Separator();
        RenderRuntimeBanner();

        if (ImGui::BeginTable("content_shell", 2, ImGuiTableFlags_NoSavedSettings)) {
            ImGui::TableSetupColumn("Chat", ImGuiTableColumnFlags_WidthStretch, 1.0f);
            ImGui::TableSetupColumn("Info", ImGuiTableColumnFlags_WidthFixed, 346.0f);
            ImGui::TableNextRow();

            ImGui::TableSetColumnIndex(0);
            RenderChatPanel();

            ImGui::TableSetColumnIndex(1);
            RenderRightPanel();

            ImGui::EndTable();
        }

        ImGui::EndTable();
    }
    ImGui::PopStyleVar();

    if (!pending_popup_.empty()) {
        ImGui::OpenPopup(pending_popup_.c_str());
        pending_popup_.clear();
    }

    if (ImGui::BeginPopupModal("Aegis Settings", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("settings_modal_body", ImVec2(700.0f, 620.0f), false);
        RenderSettingsTab();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Setup Check", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("setup_check_modal_body", ImVec2(760.0f, 620.0f), false);
        RenderSetupCheckModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Context Preview", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("context_preview_modal_body", ImVec2(820.0f, 640.0f), false);
        RenderContextPreviewModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Memory Center", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("memory_center_modal_body", ImVec2(900.0f, 640.0f), false);
        RenderMemoryCenterModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Conversations", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("conversation_browser_modal_body", ImVec2(820.0f, 620.0f), false);
        RenderConversationBrowserModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Checkpoints", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("checkpoint_browser_modal_body", ImVec2(860.0f, 620.0f), false);
        RenderCheckpointBrowserModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Model Stack", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("model_stack_modal_body", ImVec2(820.0f, 620.0f), false);
        RenderModelStackModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Build Queue", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("roadmap_modal_body", ImVec2(860.0f, 640.0f), false);
        RenderRoadmapModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Creative Studio", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("creative_studio_modal_body", ImVec2(920.0f, 640.0f), false);
        RenderCreativeStudioModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Coding Routes", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("coding_routes_modal_body", ImVec2(860.0f, 620.0f), false);
        RenderCodingRoutesModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Command Palette", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("command_palette_modal_body", ImVec2(620.0f, 520.0f), false);
        RenderCommandPaletteModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    SyncStatusToast();
    RenderToasts();
    DrawWindowControls();
    ImGui::End();
}

void AegisChatApp::HandleKeyboardShortcuts()
{
    ImGuiIO& io = ImGui::GetIO();
    const bool ctrl = io.KeyCtrl;

    if (ctrl && ImGui::IsKeyPressed(ImGuiKey_K, false)) {
        command_palette_buffer_.fill('\0');
        pending_popup_ = "Aegis Command Palette";
        command_palette_focus_ = true;
        return;
    }

    if (ctrl && ImGui::IsKeyPressed(ImGuiKey_N, false)) {
        StartNewChat();
        return;
    }

    if (ctrl && ImGui::IsKeyPressed(ImGuiKey_Comma, false)) {
        pending_popup_ = "Aegis Settings";
        status_ = "Opened settings.";
        return;
    }

    if (ctrl && ImGui::IsKeyPressed(ImGuiKey_R, false)) {
        RegenerateLastResponse();
        return;
    }

    if (ctrl && ImGui::IsKeyPressed(ImGuiKey_Enter, false) && !busy_) {
        workspace_root_ = BufferString(workspace_buffer_.data());
        SubmitMessage();
    }

    if (ImGui::IsKeyPressed(ImGuiKey_Escape, false) && busy_) {
        CancelActiveResponse();
    }
}

void AegisChatApp::PushToast(const std::string& title, const std::string& message, const std::string& tone, float duration)
{
    if (Trim(message).empty()) {
        return;
    }

    ToastNotification toast;
    toast.title = title.empty() ? "Aegis" : title;
    toast.message = message;
    toast.tone = tone.empty() ? "info" : tone;
    toast.created_at = static_cast<float>(ImGui::GetTime());
    toast.duration = std::max(1.8f, duration);
    toasts_.push_back(toast);
    if (toasts_.size() > 5) {
        toasts_.erase(toasts_.begin(), toasts_.begin() + static_cast<std::ptrdiff_t>(toasts_.size() - 5));
    }
}

void AegisChatApp::SyncStatusToast()
{
    const std::string status = Trim(status_);
    if (status.empty() || status == last_toast_status_) {
        return;
    }

    last_toast_status_ = status;
    if (!ShouldToastStatus(status)) {
        return;
    }

    const std::string tone = ToastToneForStatus(status);
    const float duration = tone == "error" ? 6.0f : (tone == "working" ? 3.2f : 4.2f);
    PushToast(ToastTitleForStatus(status), status, tone, duration);
}

void AegisChatApp::StartTask(const std::string& label, std::function<Completion()> work)
{
    if (busy_) {
        status_ = "Aegis is already working.";
        return;
    }

    busy_ = true;
    busy_label_ = label;
    status_ = label;

    active_task_ = std::async(std::launch::async, [work = std::move(work)]() mutable -> Completion {
        try {
            return work();
        } catch (const std::exception& error) {
            const std::string message = error.what();
            return [message]() {
                throw std::runtime_error(message);
            };
        }
    });
}

void AegisChatApp::AttemptLogin(bool demo_mode)
{
    std::string username = BufferString(login_user_buffer_.data());
    const std::string password = BufferString(login_password_buffer_.data());

    if (demo_mode && username.empty()) {
        username = "Demo User";
        SetBuffer(login_user_buffer_, username);
    }

    if (username.empty()) {
        login_status_ = "Enter your username to continue.";
        return;
    }

    if (!demo_mode && password.empty()) {
        login_status_ = "Enter your password to continue.";
        return;
    }

    authenticated_ = true;
    dashboard_ready_ = false;
    setup_started_ = std::chrono::steady_clock::now();
    dashboard_reveal_time_ = 0.0f;
    login_status_ = demo_mode ? "Demo desktop session accepted." : "Signed in. Preparing Aegis AI Chat.";
    status_ = "Preparing Aegis AI Chat...";
    RefreshRuntime(true);
}

void AegisChatApp::RefreshRuntime(bool allow_backend_start)
{
    AegisClient client = client_;
    const std::string preferred_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask(allow_backend_start ? "Connecting to Aegis backend..." : "Refreshing backend status...", [this, client, allow_backend_start, preferred_workspace]() mutable {
        RuntimeSnapshot snapshot = client.LoadRuntime(allow_backend_start, preferred_workspace);
        return [this, snapshot]() {
            if (!snapshot.ok) {
                health_ = {};
                status_ = snapshot.error.empty() ? "Aegis backend is offline." : snapshot.error;
                return;
            }
            ApplyRuntimeSnapshot(snapshot);
            status_ = "Backend connected.";
        };
    });
}

void AegisChatApp::StartNewChat()
{
    if (!history_.empty()) {
        SaveConversationSnapshot();
    }
    history_.clear();
    attachments_.clear();
    current_conversation_id_ = NewConversationId();
    current_conversation_title_ = "New Aegis Chat";
    current_conversation_pinned_ = false;
    current_conversation_archived_ = false;
    cancel_response_requested_ = false;
    history_.push_back({
        "assistant",
        "New chat started. Tell me what we are building next.",
        NowTimeLabel(),
        config_.model_name.empty() ? "Aegis desktop" : config_.model_name
    });
    last_response_ = {};
    has_response_ = false;
    selected_change_ = 0;
    selected_hunk_ = 0;
    status_ = "New chat started.";
    SaveConversationSnapshot();
    RefreshConversationLibrary();
}

void AegisChatApp::LoadConversationSnapshot()
{
    history_.clear();
    current_conversation_id_.clear();
    current_conversation_title_.clear();
    current_conversation_pinned_ = false;
    current_conversation_archived_ = false;

    const std::filesystem::path path = ConversationSnapshotPath();
    JsonValue root;
    std::vector<ChatMessage> messages;
    if (LoadConversationFilePayload(path, &root, &messages)) {
        history_ = std::move(messages);
        current_conversation_id_ = root["id"].AsString();
        current_conversation_title_ = root["title"].AsString();
        current_conversation_pinned_ = root["pinned"].AsBool(false);
        current_conversation_archived_ = root["archived"].AsBool(false);
        workspace_root_ = root["workspace_root"].AsString(workspace_root_);
        if (!workspace_root_.empty()) {
            SetBuffer(workspace_buffer_, workspace_root_);
        }
    }

    if (history_.empty()) {
        current_conversation_id_ = NewConversationId();
        current_conversation_title_ = "New Aegis Chat";
        history_.push_back({
            "assistant",
            "Aegis desktop is ready. Connect the backend, pick a workspace, and send me the first task.",
            NowTimeLabel(),
            "Aegis desktop"
        });
        SaveConversationSnapshot();
    } else {
        if (current_conversation_id_.empty()) {
            current_conversation_id_ = NewConversationId();
        }
        if (current_conversation_title_.empty()) {
            current_conversation_title_ = ConversationTitleFromHistory(history_);
        }
        status_ = "Restored last local conversation.";
    }
    RefreshConversationLibrary();
}

void AegisChatApp::SaveConversationSnapshot()
{
    if (current_conversation_id_.empty()) {
        current_conversation_id_ = NewConversationId();
    }
    if (current_conversation_title_.empty() || current_conversation_title_ == "New Aegis Chat") {
        current_conversation_title_ = ConversationTitleFromHistory(history_);
    }

    const std::string active_model = models_.active_model.empty() ? config_.model_name : models_.active_model;
    WriteConversationFile(
        ConversationSnapshotPath(),
        current_conversation_id_,
        current_conversation_title_,
        current_conversation_pinned_,
        current_conversation_archived_,
        history_,
        workspace_root_,
        active_model);
    WriteConversationFile(
        ConversationLibraryPath(current_conversation_id_),
        current_conversation_id_,
        current_conversation_title_,
        current_conversation_pinned_,
        current_conversation_archived_,
        history_,
        workspace_root_,
        active_model);
}

void AegisChatApp::RefreshConversationLibrary()
{
    conversations_.clear();
    const std::filesystem::path dir = ConversationLibraryDirectory();
    std::error_code ec;
    std::filesystem::create_directories(dir, ec);
    if (!std::filesystem::exists(dir, ec)) {
        return;
    }

    for (const std::filesystem::directory_entry& entry : std::filesystem::directory_iterator(dir, ec)) {
        if (ec || !entry.is_regular_file(ec) || entry.path().extension() != L".json") {
            continue;
        }

        JsonValue root;
        std::vector<ChatMessage> messages;
        if (!LoadConversationFilePayload(entry.path(), &root, &messages) || messages.empty()) {
            continue;
        }

        LocalConversationSummary summary;
        summary.id = root["id"].AsString(entry.path().stem().string());
        summary.title = root["title"].AsString();
        if (summary.title.empty()) {
            summary.title = ConversationTitleFromHistory(messages);
        }
        summary.preview = root["preview"].AsString();
        if (summary.preview.empty()) {
            summary.preview = ConversationPreviewFromHistory(messages);
        }
        summary.saved_at = root["saved_at"].AsString();
        summary.path = WideToUtf8(entry.path().wstring());
        summary.message_count = static_cast<int>(messages.size());
        summary.pinned = root["pinned"].AsBool(false);
        summary.archived = root["archived"].AsBool(false);
        summary.sort_key = FileSortKey(entry.path());
        conversations_.push_back(std::move(summary));
    }

    std::sort(conversations_.begin(), conversations_.end(), [](const LocalConversationSummary& left, const LocalConversationSummary& right) {
        if (left.pinned != right.pinned) {
            return left.pinned > right.pinned;
        }
        return left.sort_key > right.sort_key;
    });
}

void AegisChatApp::LoadConversationFromLibrary(int index)
{
    if (index < 0 || index >= static_cast<int>(conversations_.size())) {
        status_ = "No conversation selected.";
        return;
    }

    const LocalConversationSummary summary = conversations_[index];
    JsonValue root;
    std::vector<ChatMessage> messages;
    if (!LoadConversationFilePayload(std::filesystem::path(Utf8ToWide(summary.path)), &root, &messages) || messages.empty()) {
        status_ = "Could not load conversation.";
        return;
    }

    history_ = std::move(messages);
    attachments_.clear();
    current_conversation_id_ = root["id"].AsString(summary.id);
    current_conversation_title_ = root["title"].AsString(summary.title);
    if (current_conversation_title_.empty()) {
        current_conversation_title_ = ConversationTitleFromHistory(history_);
    }
    current_conversation_pinned_ = root["pinned"].AsBool(summary.pinned);
    current_conversation_archived_ = root["archived"].AsBool(summary.archived);
    workspace_root_ = root["workspace_root"].AsString(workspace_root_);
    if (!workspace_root_.empty()) {
        SetBuffer(workspace_buffer_, workspace_root_);
    }
    last_response_ = {};
    has_response_ = false;
    selected_change_ = 0;
    selected_hunk_ = 0;
    SaveConversationSnapshot();
    RefreshConversationLibrary();
    status_ = "Loaded conversation: " + current_conversation_title_;
}

void AegisChatApp::DeleteConversationFromLibrary(int index)
{
    if (index < 0 || index >= static_cast<int>(conversations_.size())) {
        status_ = "No conversation selected.";
        return;
    }

    const LocalConversationSummary summary = conversations_[index];
    std::error_code ec;
    std::filesystem::remove(std::filesystem::path(Utf8ToWide(summary.path)), ec);
    if (ec) {
        status_ = "Could not delete conversation.";
        return;
    }

    if (summary.id == current_conversation_id_) {
        history_.clear();
        attachments_.clear();
        current_conversation_id_ = NewConversationId();
        current_conversation_title_ = "New Aegis Chat";
        current_conversation_pinned_ = false;
        current_conversation_archived_ = false;
        history_.push_back({
            "assistant",
            "Deleted the open conversation. Tell me what we are building next.",
            NowTimeLabel(),
            config_.model_name.empty() ? "Aegis desktop" : config_.model_name
        });
        SaveConversationSnapshot();
        RefreshConversationLibrary();
        status_ = "Deleted open conversation and started a new chat.";
    } else {
        RefreshConversationLibrary();
        status_ = "Deleted conversation.";
    }
}

void AegisChatApp::ToggleConversationPinned(int index)
{
    if (index < 0 || index >= static_cast<int>(conversations_.size())) {
        return;
    }
    LocalConversationSummary summary = conversations_[index];
    JsonValue root;
    std::vector<ChatMessage> messages;
    if (!LoadConversationFilePayload(std::filesystem::path(Utf8ToWide(summary.path)), &root, &messages)) {
        status_ = "Could not update conversation.";
        return;
    }
    summary.pinned = !summary.pinned;
    WriteConversationFile(
        std::filesystem::path(Utf8ToWide(summary.path)),
        summary.id,
        summary.title,
        summary.pinned,
        summary.archived,
        messages,
        root["workspace_root"].AsString(workspace_root_),
        root["active_model"].AsString(config_.model_name));
    if (summary.id == current_conversation_id_) {
        current_conversation_pinned_ = summary.pinned;
        SaveConversationSnapshot();
    }
    RefreshConversationLibrary();
    status_ = summary.pinned ? "Pinned conversation." : "Unpinned conversation.";
}

void AegisChatApp::ToggleConversationArchived(int index)
{
    if (index < 0 || index >= static_cast<int>(conversations_.size())) {
        return;
    }
    LocalConversationSummary summary = conversations_[index];
    JsonValue root;
    std::vector<ChatMessage> messages;
    if (!LoadConversationFilePayload(std::filesystem::path(Utf8ToWide(summary.path)), &root, &messages)) {
        status_ = "Could not update conversation.";
        return;
    }
    summary.archived = !summary.archived;
    WriteConversationFile(
        std::filesystem::path(Utf8ToWide(summary.path)),
        summary.id,
        summary.title,
        summary.pinned,
        summary.archived,
        messages,
        root["workspace_root"].AsString(workspace_root_),
        root["active_model"].AsString(config_.model_name));
    if (summary.id == current_conversation_id_) {
        current_conversation_archived_ = summary.archived;
        SaveConversationSnapshot();
    }
    RefreshConversationLibrary();
    status_ = summary.archived ? "Archived conversation." : "Restored conversation.";
}

void AegisChatApp::ExportConversationMarkdown()
{
    if (history_.empty()) {
        status_ = "There is no conversation to export yet.";
        return;
    }

    const std::filesystem::path path = ConversationExportPath();
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
        status_ = "Could not export conversation.";
        return;
    }

    file << "# Aegis Chat Export\n\n";
    file << "- Exported: " << NowTimeLabel() << "\n";
    file << "- Messages: " << history_.size() << "\n";
    if (!workspace_root_.empty()) {
        file << "- Workspace: `" << workspace_root_ << "`\n";
    }
    const std::string active_model = models_.active_model.empty() ? config_.model_name : models_.active_model;
    if (!active_model.empty()) {
        file << "- Active model: `" << active_model << "`\n";
    }
    file << "\n---\n\n";

    for (const ChatMessage& message : history_) {
        if (Trim(message.content).empty()) {
            continue;
        }
        const std::string role = message.role == "user" ? "You" : (config_.assistant_name.empty() ? "Aegis AI" : config_.assistant_name);
        file << "## " << role;
        if (!message.time_label.empty()) {
            file << " - " << message.time_label;
        }
        if (!message.model_label.empty()) {
            file << " via " << message.model_label;
        }
        file << "\n\n";
        file << message.content << "\n\n";
    }

    status_ = "Exported conversation: " + WideToUtf8(path.wstring());
    OpenExternalPath(path);
}

void AegisChatApp::CopyPatchToClipboard()
{
    if (!has_response_ || last_response_.changes.empty()) {
        status_ = "There are no generated changes to copy.";
        return;
    }

    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string patch = BuildPatchText(last_response_, workspace);
    ImGui::SetClipboardText(patch.c_str());
    status_ = "Copied generated patch package.";
}

void AegisChatApp::ExportPatchFile()
{
    if (!has_response_ || last_response_.changes.empty()) {
        status_ = "There are no generated changes to export.";
        return;
    }

    const std::filesystem::path path = PatchExportPath();
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
        status_ = "Could not export patch package.";
        return;
    }

    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    file << BuildPatchText(last_response_, workspace);
    file.close();

    status_ = "Exported patch package: " + WideToUtf8(path.wstring());
    OpenExternalPath(path);
}

void AegisChatApp::ExportSelectedMediaJob()
{
    if (!has_selected_media_job_ || selected_media_job_.job_dir.empty()) {
        status_ = "Select a Creative Studio job with a package folder before exporting.";
        PushToast("Creative export", status_, "warning");
        return;
    }

    const std::filesystem::path source(Utf8ToWide(selected_media_job_.job_dir));
    std::error_code ec;
    if (!std::filesystem::exists(source, ec) || !std::filesystem::is_directory(source, ec)) {
        status_ = "Creative Studio package folder was not found.";
        PushToast("Creative export failed", status_, "error");
        return;
    }

    const std::filesystem::path destination = CreativeJobExportPath(selected_media_job_);
    std::filesystem::create_directories(destination.parent_path(), ec);
    ec.clear();
    std::filesystem::copy(
        source,
        destination,
        std::filesystem::copy_options::recursive |
            std::filesystem::copy_options::overwrite_existing |
            std::filesystem::copy_options::copy_symlinks,
        ec);
    if (ec) {
        status_ = "Could not export Creative Studio package: " + ec.message();
        PushToast("Creative export failed", ec.message(), "error");
        return;
    }

    status_ = "Exported Creative Studio package: " + WideToUtf8(destination.wstring());
    PushToast("Creative package exported", WideToUtf8(destination.wstring()), "success");
    OpenExternalPath(destination);
}

void AegisChatApp::ExportCreativeAsset(const MediaAssetInfo& asset)
{
    if (Trim(asset.path).empty()) {
        status_ = "Select a Creative Studio asset before exporting.";
        PushToast("Creative export", status_, "warning");
        return;
    }

    const std::filesystem::path source(Utf8ToWide(asset.path));
    std::error_code ec;
    if (!std::filesystem::exists(source, ec) || !std::filesystem::is_regular_file(source, ec)) {
        status_ = "Creative Studio asset file was not found.";
        PushToast("Creative export failed", status_, "error");
        return;
    }

    const std::filesystem::path destination = CreativeAssetExportPath(asset, selected_media_job_.id);
    std::filesystem::create_directories(destination.parent_path(), ec);
    ec.clear();
    std::filesystem::copy_file(source, destination, std::filesystem::copy_options::overwrite_existing, ec);
    if (ec) {
        status_ = "Could not export Creative Studio asset: " + ec.message();
        PushToast("Creative export failed", ec.message(), "error");
        return;
    }

    status_ = "Exported Creative Studio asset: " + WideToUtf8(destination.wstring());
    PushToast("Creative asset exported", WideToUtf8(destination.wstring()), "success");
    OpenExternalPath(destination.parent_path());
}

void AegisChatApp::SaveDesktopSettingsFromUi()
{
    DesktopSettings next = BuildDesktopSettingsFromBuffers();
    StartTask("Saving desktop settings...", [this, next]() {
        std::string error;
        if (!SaveDesktopSettings(next, error)) {
            throw std::runtime_error(error);
        }
        return [this, next]() {
            settings_ = next;
            client_.SetSettings(settings_);
            HydrateDesktopBuffers();
            status_ = "Desktop settings saved.";
            next_health_check_ = std::chrono::steady_clock::now();
        };
    });
}

void AegisChatApp::SaveRemoteConfigFromUi()
{
    AegisClient client = client_;
    AppConfig next = BuildConfigFromBuffers();
    StartTask("Saving Aegis settings...", [this, client, next]() mutable {
        AppConfig saved = client.SaveConfig(next);
        ModelInventory models;
        try {
            models = client.GetModels();
        } catch (const std::exception& error) {
            models.active_model = saved.model_name;
            models.active_api = saved.model_api;
            models.active_endpoint = saved.model_endpoint;
            models.message = error.what();
        }
        std::string resolved_root;
        std::vector<WorkspaceFile> files = client.ListFiles(saved.default_workspace, client.Settings().max_files, &resolved_root);
        std::vector<TaskSummary> tasks = client.GetHistory(resolved_root, 8);
        return [this, saved, models = std::move(models), resolved_root, files = std::move(files), tasks = std::move(tasks)]() {
            config_ = saved;
            models_ = models;
            has_config_ = true;
            workspace_root_ = resolved_root;
            config_.default_workspace = resolved_root;
            files_ = files;
            recent_tasks_ = tasks;
            mode_ = config_.default_mode;
            HydrateConfigBuffers();
            status_ = "Aegis settings saved.";
        };
    });
}

void AegisChatApp::SelectModelFromInventory(const ModelInfo& model)
{
    const std::string name = Trim(model.name.empty() ? model.id : model.name);
    if (name.empty()) {
        status_ = "This model record has no selectable name.";
        return;
    }

    SetBuffer(model_name_buffer_, name);
    if (!Trim(model.api).empty()) {
        SetBuffer(model_api_buffer_, model.api);
    }
    if (!Trim(model.endpoint).empty()) {
        SetBuffer(model_endpoint_buffer_, model.endpoint);
    }

    config_.model_name = BufferString(model_name_buffer_.data());
    config_.model_api = BufferString(model_api_buffer_.data());
    config_.model_endpoint = BufferString(model_endpoint_buffer_.data());
    status_ = "Selecting model: " + config_.model_name + ".";
    SaveRemoteConfigFromUi();
}

void AegisChatApp::HydrateModelProviderEditor(const ModelRegistryProviderInfo* provider, int index)
{
    show_model_provider_editor_ = true;
    selected_model_provider_index_ = index;
    if (provider == nullptr) {
        SetBuffer(provider_id_buffer_, "custom:provider");
        SetBuffer(provider_label_buffer_, "Custom Provider");
        SetBuffer(provider_api_buffer_, "openai-compatible");
        SetBuffer(provider_endpoint_buffer_, "");
        SetBuffer(provider_capabilities_buffer_, "chat, code");
        SetBuffer(provider_roles_buffer_, "chat, fallback");
        SetBuffer(provider_health_buffer_, "planned");
        SetBuffer(provider_notes_buffer_, "Add endpoint and model routing notes here.");
        model_provider_local_ = false;
        model_provider_enabled_ = true;
        model_provider_configured_ = false;
        return;
    }

    SetBuffer(provider_id_buffer_, provider->id);
    SetBuffer(provider_label_buffer_, provider->label.empty() ? provider->id : provider->label);
    SetBuffer(provider_api_buffer_, provider->api);
    SetBuffer(provider_endpoint_buffer_, provider->endpoint);
    SetBuffer(provider_capabilities_buffer_, JoinPalette(provider->capabilities));
    SetBuffer(provider_roles_buffer_, JoinPalette(provider->roles));
    SetBuffer(provider_health_buffer_, provider->health.empty() ? "unknown" : provider->health);
    SetBuffer(provider_notes_buffer_, provider->notes);
    model_provider_local_ = provider->local;
    model_provider_enabled_ = provider->enabled;
    model_provider_configured_ = provider->configured;
}

void AegisChatApp::SaveModelProviderFromEditor()
{
    ModelRegistryProviderInfo provider;
    provider.id = BufferString(provider_id_buffer_.data());
    provider.label = BufferString(provider_label_buffer_.data());
    provider.api = BufferString(provider_api_buffer_.data());
    provider.endpoint = BufferString(provider_endpoint_buffer_.data());
    provider.local = model_provider_local_;
    provider.enabled = model_provider_enabled_;
    provider.configured = model_provider_configured_;
    provider.capabilities = SplitCommaList(BufferString(provider_capabilities_buffer_.data()));
    provider.roles = SplitCommaList(BufferString(provider_roles_buffer_.data()));
    provider.health = BufferString(provider_health_buffer_.data());
    provider.notes = BufferString(provider_notes_buffer_.data());

    if (provider.id.empty()) {
        status_ = "Provider id is required.";
        PushToast("Provider not saved", "Provider id is required.", "error");
        return;
    }

    AegisClient client = client_;
    StartTask("Saving model provider...", [this, client, provider]() mutable {
        ModelRegistrySnapshot saved = client.SaveModelRegistryProvider(provider);
        return [this, saved = std::move(saved), provider_id = provider.id]() {
            model_registry_ = saved;
            selected_model_provider_index_ = -1;
            for (int i = 0; i < static_cast<int>(model_registry_.providers.size()); ++i) {
                if (model_registry_.providers[i].id == provider_id) {
                    selected_model_provider_index_ = i;
                    HydrateModelProviderEditor(&model_registry_.providers[i], i);
                    break;
                }
            }
            status_ = "Saved model provider: " + provider_id + ".";
            PushToast("Provider saved", provider_id, "success");
        };
    });
}

void AegisChatApp::DeleteSelectedModelProvider()
{
    if (selected_model_provider_index_ < 0 || selected_model_provider_index_ >= static_cast<int>(model_registry_.providers.size())) {
        status_ = "Select a provider to delete.";
        return;
    }

    const std::string provider_id = model_registry_.providers[selected_model_provider_index_].id;
    if (provider_id == model_registry_.active_provider_id) {
        status_ = "The active provider cannot be deleted.";
        PushToast("Provider not deleted", "The active provider cannot be deleted.", "error");
        return;
    }

    AegisClient client = client_;
    StartTask("Deleting model provider...", [this, client, provider_id]() mutable {
        ModelRegistrySnapshot saved = client.DeleteModelRegistryProvider(provider_id);
        return [this, saved = std::move(saved), provider_id]() {
            model_registry_ = saved;
            show_model_provider_editor_ = false;
            selected_model_provider_index_ = -1;
            status_ = "Deleted model provider: " + provider_id + ".";
            PushToast("Provider deleted", provider_id, "success");
        };
    });
}

void AegisChatApp::UseValidationSuggestion(const ValidationSuggestionInfo& suggestion)
{
    SetBuffer(validation_command_buffer_, suggestion.command);
    SetBuffer(validation_label_buffer_, suggestion.label.empty() ? suggestion.command : suggestion.label);
    SetBuffer(validation_notes_buffer_, suggestion.reason);
    status_ = "Selected validation command: " + suggestion.command + ".";
}

void AegisChatApp::RenderValidationSuggestionTable(
    const char* table_id,
    const std::vector<ValidationSuggestionInfo>& suggestions,
    int max_count)
{
    if (suggestions.empty()) {
        return;
    }

    ImGui::PushID(table_id);
    if (ImGui::BeginTable(table_id, 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Command");
        ImGui::TableSetupColumn("Category", ImGuiTableColumnFlags_WidthFixed, 112.0f);
        ImGui::TableSetupColumn("Why");
        ImGui::TableSetupColumn("Use", ImGuiTableColumnFlags_WidthFixed, 54.0f);
        ImGui::TableHeadersRow();
        const int count = std::min(max_count, static_cast<int>(suggestions.size()));
        for (int i = 0; i < count; ++i) {
            const ValidationSuggestionInfo& suggestion = suggestions[i];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(suggestion.command, 54));
            ImGui::TableSetColumnIndex(1);
            TextMuted(suggestion.category);
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(suggestion.reason, 86));
            ImGui::TableSetColumnIndex(3);
            if (ImGui::Button("Use")) {
                UseValidationSuggestion(suggestion);
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
    ImGui::PopID();
}

void AegisChatApp::SubmitMessage(const std::string& override_message, bool append_user_message)
{
    const std::string raw_content = Trim(override_message.empty() ? std::string(message_buffer_.data()) : override_message);
    if (raw_content.empty() && (attachments_.empty() || !append_user_message)) {
        return;
    }

    const std::string explicit_workspace = ExtractWindowsPathFromPrompt(raw_content);
    if (!explicit_workspace.empty()) {
        workspace_root_ = explicit_workspace;
        SetBuffer(workspace_buffer_, workspace_root_);
    }

    const std::vector<FileContent> attachments = append_user_message ? attachments_ : std::vector<FileContent>{};
    const std::string content = BuildMessageWithAttachments(raw_content, attachments);
    std::string display_content = raw_content.empty() ? "Use the attached workspace file(s) as context." : raw_content;
    if (!attachments.empty()) {
        display_content += "\n\n" + AttachmentSummary(attachments);
    }

    if (append_user_message) {
        ChatMessage user_message{"user", display_content, NowTimeLabel()};
        history_.push_back(user_message);
        attachments_.clear();
        SaveConversationSnapshot();
    }
    message_buffer_.fill('\0');

    AegisClient client = client_;
    const std::vector<ChatMessage> request_history = history_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string mode = mode_;
    const bool auto_apply = ShouldAutoApplyPrompt(raw_content);
    const bool apply = apply_changes_ || auto_apply;
    const bool validate = run_validation_;
    const int repairs = max_repairs_;
    cancel_response_requested_ = false;
    if (!explicit_workspace.empty()) {
        status_ = "Using requested workspace: " + Shorten(explicit_workspace, 112);
    }

    const std::string task_label = apply ? "Aegis is creating and applying files..." : "Aegis is thinking...";
    StartTask(task_label, [this, client, content, request_history, workspace, mode, apply, validate, repairs, auto_apply]() mutable {
        AgentResponse response = client.SendMessage(content, request_history, workspace, mode, apply, validate, repairs);
        return [this, response = std::move(response), auto_apply]() {
            if (cancel_response_requested_) {
                cancel_response_requested_ = false;
                status_ = "Generation canceled. The last user message stayed in the transcript.";
                SaveConversationSnapshot();
                return;
            }
            last_response_ = response;
            has_response_ = true;
            selected_change_ = 0;
            selected_hunk_ = 0;
            if (!response.workspace_root.empty()) {
                workspace_root_ = response.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            if (!response.workspace_files.empty()) {
                files_ = response.workspace_files;
            }
            if (!response.recent_tasks.empty()) {
                recent_tasks_ = response.recent_tasks;
            }
            if (response.has_validation_profile) {
                validation_profile_.workspace_root = response.workspace_root;
                validation_profile_.profile = response.validation_profile;
                validation_profile_.has_profile = true;
                has_validation_profile_snapshot_ = true;
                SetBuffer(validation_command_buffer_, response.validation_profile.command);
                SetBuffer(validation_label_buffer_, response.validation_profile.label);
                SetBuffer(validation_notes_buffer_, response.validation_profile.notes);
            }
            const std::string assistant_name = response.assistant_name.empty() ? "Aegis AI" : response.assistant_name;
            std::string model_label = response.engine;
            if (Trim(model_label).empty()) {
                model_label = models_.active_model.empty() ? config_.model_name : models_.active_model;
            }
            if (Trim(model_label).empty()) {
                model_label = config_.model_api.empty() ? "configured model" : config_.model_api;
            }
            history_.push_back({"assistant", BuildAssistantSummary(response), NowTimeLabel(), model_label});
            SaveConversationSnapshot();
            if (response.has_validation && ValidationFailed(response)) {
                status_ = "Validation still needs attention. Open Response for output or use Fix Validation again.";
            } else if (!response.repair_attempts.empty()) {
                status_ = "Repair loop finished with " + std::to_string(response.repair_attempts.size()) + " attempt(s).";
            } else if (!response.applied.empty()) {
                status_ = "Applied " + std::to_string(response.applied.size()) + " file change(s) in " + Shorten(workspace_root_, 92) + ".";
            } else if (!response.changes.empty()) {
                status_ = "Generated " + std::to_string(response.changes.size()) + " change(s). Open Changes to review or apply them.";
            } else if (auto_apply) {
                status_ = assistant_name + " responded, but no file changes came back.";
            } else {
                status_ = assistant_name + " responded.";
            }
        };
    });
}

void AegisChatApp::RegenerateLastResponse()
{
    if (busy_) {
        status_ = "Aegis is already working.";
        return;
    }

    const std::string prompt = LatestUserPrompt(history_);
    if (Trim(prompt).empty()) {
        status_ = "No user message to retry yet.";
        return;
    }

    bool removed_assistant = false;
    while (!history_.empty() && history_.back().role == "assistant") {
        history_.pop_back();
        removed_assistant = true;
    }

    if (removed_assistant) {
        last_response_ = {};
        has_response_ = false;
        SaveConversationSnapshot();
        status_ = "Regenerating last response with the selected model.";
    } else {
        status_ = "Retrying last user message with the selected model.";
    }

    SubmitMessage(prompt, false);
}

void AegisChatApp::CancelActiveResponse()
{
    if (!busy_) {
        status_ = "There is no active response to cancel.";
        return;
    }

    cancel_response_requested_ = true;
    busy_label_ = "Canceling response...";
    status_ = "Cancel requested. Waiting for the current backend call to return.";
}

void AegisChatApp::AttachSelectedFile()
{
    if (!has_selected_file_) {
        status_ = "Select a text file in the Workspace panel before attaching.";
        return;
    }

    if (Trim(selected_file_.content).empty()) {
        status_ = "Selected file is empty.";
        return;
    }

    for (const FileContent& attachment : attachments_) {
        if (attachment.workspace_root == selected_file_.workspace_root && attachment.path == selected_file_.path) {
            status_ = "File is already attached.";
            return;
        }
    }

    if (attachments_.size() >= 6) {
        status_ = "Attachment tray is full. Remove a file before adding another.";
        return;
    }

    attachments_.push_back(selected_file_);
    status_ = "Attached " + selected_file_.path + " to the next message.";
}

void AegisChatApp::RemoveAttachment(size_t index)
{
    if (index >= attachments_.size()) {
        return;
    }
    const std::string path = attachments_[index].path;
    attachments_.erase(attachments_.begin() + static_cast<std::ptrdiff_t>(index));
    status_ = "Removed attachment: " + path + ".";
}

void AegisChatApp::ApplyPendingChanges()
{
    if (!has_response_ || last_response_.changes.empty()) {
        status_ = "There are no pending changes to apply.";
        return;
    }
    if (ResponseChangesFullyApplied(last_response_)) {
        status_ = "Latest generated changes are already applied.";
        return;
    }

    std::vector<FileChange> changes;
    for (const FileChange& change : last_response_.changes) {
        if (!ChangeAlreadyApplied(last_response_, change)) {
            changes.push_back(change);
        }
    }
    if (changes.empty()) {
        status_ = "Latest generated changes are already applied.";
        return;
    }

    AegisClient client = client_;
    const std::string workspace = workspace_root_;
    StartTask("Applying previewed changes...", [this, client, workspace, changes]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, changes);
        return [this, result = std::move(result)]() {
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            files_ = result.workspace_files;
            AppendUniqueAppliedEntries(last_response_.applied, result.applied);
            last_response_.checkpoint = result.checkpoint;
            last_response_.warnings.insert(last_response_.warnings.end(), result.warnings.begin(), result.warnings.end());
            status_ = result.applied.empty() ? "No changes were applied." : "Applied " + std::to_string(result.applied.size()) + " change(s).";
        };
    });
}

void AegisChatApp::ApplySelectedChange()
{
    if (!has_response_ || last_response_.changes.empty()) {
        status_ = "There is no selected generated change to apply.";
        return;
    }
    selected_change_ = std::max(0, std::min(selected_change_, static_cast<int>(last_response_.changes.size()) - 1));
    const FileChange change = last_response_.changes[static_cast<size_t>(selected_change_)];
    if (ChangeAlreadyApplied(last_response_, change)) {
        status_ = "Selected change is already applied.";
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Applying selected file change...", [this, client, workspace, change]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, std::vector<FileChange>{change});
        return [this, result = std::move(result), path = change.path]() {
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            files_ = result.workspace_files;
            AppendUniqueAppliedEntries(last_response_.applied, result.applied);
            last_response_.checkpoint = result.checkpoint;
            last_response_.warnings.insert(last_response_.warnings.end(), result.warnings.begin(), result.warnings.end());
            status_ = result.applied.empty()
                ? "No change was applied for " + Shorten(path, 64) + "."
                : "Applied selected file: " + Shorten(path, 74) + ".";
        };
    });
}

void AegisChatApp::ApplySelectedHunk()
{
    if (!has_response_ || last_response_.changes.empty()) {
        status_ = "There is no selected hunk to apply.";
        return;
    }

    selected_change_ = std::max(0, std::min(selected_change_, static_cast<int>(last_response_.changes.size()) - 1));
    const FileChange source_change = last_response_.changes[static_cast<size_t>(selected_change_)];
    if (ChangeAlreadyApplied(last_response_, source_change)) {
        status_ = "Selected file is already fully applied.";
        return;
    }

    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    FileChange hunk_change;
    std::string hunk_error;
    if (!BuildSelectedHunkChange(source_change, workspace, selected_hunk_, hunk_change, hunk_error)) {
        status_ = hunk_error;
        return;
    }

    AegisClient client = client_;
    const int hunk_number = selected_hunk_ + 1;
    StartTask("Applying selected diff hunk...", [this, client, workspace, hunk_change, source_path = source_change.path, hunk_number]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, std::vector<FileChange>{hunk_change});
        return [this, result = std::move(result), source_path, hunk_number]() {
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            files_ = result.workspace_files;
            last_response_.checkpoint = result.checkpoint;
            last_response_.warnings.insert(last_response_.warnings.end(), result.warnings.begin(), result.warnings.end());
            status_ = result.applied.empty()
                ? "No change was applied for hunk " + std::to_string(hunk_number) + "."
                : "Applied hunk " + std::to_string(hunk_number) + " from " + Shorten(source_path, 72) + ".";
        };
    });
}

void AegisChatApp::RollbackLastApply()
{
    if (!has_response_ || last_response_.checkpoint.empty()) {
        status_ = "No applied checkpoint is available to roll back.";
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string checkpoint = last_response_.checkpoint;
    StartTask("Restoring last file checkpoint...", [this, client, workspace, checkpoint]() mutable {
        RestoreResult result = client.RestoreCheckpoint(workspace, checkpoint);
        return [this, result = std::move(result), checkpoint]() {
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            files_ = result.workspace_files;
            RemoveAppliedEntriesForRestoredFiles(last_response_.applied, result.restored);
            last_response_.checkpoint.clear();
            last_response_.warnings.insert(last_response_.warnings.end(), result.warnings.begin(), result.warnings.end());
            const std::string note = result.restored.empty()
                ? "Checkpoint restore finished without file changes."
                : "Rolled back " + std::to_string(result.restored.size()) + " file item(s) from checkpoint " + Shorten(checkpoint, 24) + ".";
            status_ = note;
        };
    });
}

void AegisChatApp::RefreshCheckpoints()
{
    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Loading workspace checkpoints...", [this, client, workspace]() mutable {
        CheckpointListResult result = client.ListCheckpoints(workspace, 80);
        return [this, result = std::move(result)]() mutable {
            checkpoints_ = std::move(result);
            if (!checkpoints_.workspace_root.empty()) {
                workspace_root_ = checkpoints_.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            if (checkpoints_.checkpoints.empty()) {
                selected_checkpoint_index_ = -1;
                status_ = "No checkpoints found for this workspace.";
                return;
            }
            selected_checkpoint_index_ = std::max(
                0,
                std::min(selected_checkpoint_index_ < 0 ? 0 : selected_checkpoint_index_, static_cast<int>(checkpoints_.checkpoints.size()) - 1));
            status_ = "Loaded " + std::to_string(checkpoints_.checkpoints.size()) + " checkpoint(s).";
        };
    });
}

void AegisChatApp::RestoreCheckpointFromBrowser()
{
    if (checkpoints_.checkpoints.empty()) {
        status_ = "No checkpoint is selected.";
        return;
    }

    selected_checkpoint_index_ = std::max(
        0,
        std::min(selected_checkpoint_index_, static_cast<int>(checkpoints_.checkpoints.size()) - 1));
    const CheckpointSummaryInfo checkpoint = checkpoints_.checkpoints[static_cast<size_t>(selected_checkpoint_index_)];
    if (checkpoint.id.empty()) {
        status_ = "Selected checkpoint has no restore id.";
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Restoring selected checkpoint...", [this, client, workspace, checkpoint]() mutable {
        RestoreResult result = client.RestoreCheckpoint(workspace, checkpoint.id);
        return [this, result = std::move(result), checkpoint]() {
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            files_ = result.workspace_files;
            if (has_response_) {
                RemoveAppliedEntriesForRestoredFiles(last_response_.applied, result.restored);
                if (last_response_.checkpoint == checkpoint.id) {
                    last_response_.checkpoint.clear();
                }
                last_response_.warnings.insert(last_response_.warnings.end(), result.warnings.begin(), result.warnings.end());
            }

            const std::string note = result.restored.empty()
                ? "Checkpoint restore finished without file changes."
                : "Restored " + std::to_string(result.restored.size()) + " file item(s) from " + Shorten(checkpoint.id, 24) + ".";
            status_ = note;
        };
    });
}

void AegisChatApp::ValidateWorkspace()
{
    AegisClient client = client_;
    const std::string workspace = workspace_root_;
    StartTask("Running workspace validation...", [this, client, workspace]() mutable {
        AgentResponse response = client.ValidateWorkspace(workspace);
        return [this, response = std::move(response)]() {
            if (!has_response_) {
                last_response_ = response;
                has_response_ = true;
            } else {
                last_response_.validation = response.validation;
                last_response_.has_validation = response.has_validation;
                last_response_.events = response.events;
                last_response_.warnings.insert(last_response_.warnings.end(), response.warnings.begin(), response.warnings.end());
            }
            if (response.has_validation_profile) {
                validation_profile_.workspace_root = response.workspace_root;
                validation_profile_.profile = response.validation_profile;
                validation_profile_.has_profile = true;
                has_validation_profile_snapshot_ = true;
                SetBuffer(validation_command_buffer_, response.validation_profile.command);
                SetBuffer(validation_label_buffer_, response.validation_profile.label);
                SetBuffer(validation_notes_buffer_, response.validation_profile.notes);
            }
            status_ = ValidationFailed(last_response_)
                ? "Validation failed. Use Fix Validation to start a repair pass."
                : "Validation passed.";
        };
    });
}

void AegisChatApp::RepairLastValidationFailure()
{
    if (busy_) {
        status_ = "Aegis is already working.";
        return;
    }
    if (!has_response_ || !ValidationFailed(last_response_)) {
        status_ = "No failing validation result is available to repair.";
        return;
    }

    apply_changes_ = true;
    run_validation_ = true;
    max_repairs_ = std::max(1, max_repairs_);
    status_ = "Starting validation repair loop.";
    SubmitMessage(BuildValidationRepairPrompt(last_response_));
}

void AegisChatApp::RecordFeedback(const std::string& sentiment, const std::string& content, const std::string& context)
{
    std::string feedback_content = Trim(content);
    if (feedback_content.empty()) {
        status_ = "No content to record.";
        return;
    }
    if (feedback_content.size() > 12000) {
        feedback_content = feedback_content.substr(0, 12000) + "\n...[feedback truncated by desktop client]";
    }

    AegisClient client = client_;
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    StartTask("Recording feedback...", [this, client, workspace, sentiment, feedback_content, context]() mutable {
        client.RecordFeedback(workspace, sentiment, feedback_content, context);
        return [this, sentiment]() {
            status_ = "Feedback recorded as project memory: " + sentiment + ".";
        };
    });
}

void AegisChatApp::RecordMessageFeedback(const ChatMessage& message, const std::string& sentiment)
{
    const std::string context = "message; role=" + message.role + "; time=" + message.time_label;
    RecordFeedback(sentiment, message.content, context);
}

void AegisChatApp::RefreshMemoryNotes()
{
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    AegisClient client = client_;
    StartTask("Loading memory center...", [this, client, workspace]() mutable {
        MemoryListResult result = client.ListMemoryNotes(workspace);
        return [this, result = std::move(result)]() {
            memory_notes_ = result.notes;
            memory_notes_loaded_ = true;
            if (!result.workspace_root.empty()) {
                workspace_root_ = result.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            if (!memory_notes_.empty()) {
                selected_memory_note_index_ = std::clamp(selected_memory_note_index_, 0, static_cast<int>(memory_notes_.size()) - 1);
                HydrateMemoryEditor(&memory_notes_[selected_memory_note_index_], selected_memory_note_index_);
            } else {
                selected_memory_note_index_ = -1;
                HydrateMemoryEditor(nullptr, -1);
            }
            status_ = "Loaded " + std::to_string(memory_notes_.size()) + " memory note(s).";
        };
    });
}

void AegisChatApp::HydrateMemoryEditor(const MemoryNoteInfo* note, int index)
{
    selected_memory_note_index_ = index;
    if (note == nullptr) {
        SetBuffer(memory_title_buffer_, "");
        SetBuffer(memory_category_buffer_, "preference");
        SetBuffer(memory_content_buffer_, "");
        SetBuffer(memory_tags_buffer_, "");
        SetBuffer(memory_related_files_buffer_, "");
        memory_note_pinned_ = false;
        memory_note_confidence_ = 0.8;
        return;
    }

    SetBuffer(memory_title_buffer_, note->title);
    SetBuffer(memory_category_buffer_, note->category.empty() ? "insight" : note->category);
    SetBuffer(memory_content_buffer_, note->content);
    SetBuffer(memory_tags_buffer_, JoinPalette(note->tags));
    SetBuffer(memory_related_files_buffer_, JoinPalette(note->related_files));
    memory_note_pinned_ = note->pinned;
    memory_note_confidence_ = note->confidence;
}

void AegisChatApp::SaveMemoryNoteFromEditor()
{
    MemoryNoteInfo note;
    if (selected_memory_note_index_ >= 0 && selected_memory_note_index_ < static_cast<int>(memory_notes_.size())) {
        note.id = memory_notes_[selected_memory_note_index_].id;
    }
    note.title = BufferString(memory_title_buffer_.data());
    note.category = BufferString(memory_category_buffer_.data());
    note.content = BufferString(memory_content_buffer_.data());
    note.pinned = memory_note_pinned_;
    note.tags = SplitCommaList(BufferString(memory_tags_buffer_.data()));
    note.related_files = SplitCommaList(BufferString(memory_related_files_buffer_.data()));
    note.confidence = memory_note_confidence_;

    if (note.title.empty() || note.content.empty()) {
        status_ = "Memory title and content are required.";
        PushToast("Memory not saved", "Add a title and content first.", "error");
        return;
    }

    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    AegisClient client = client_;
    StartTask(note.id.empty() ? "Creating memory note..." : "Saving memory note...", [this, client, workspace, note]() mutable {
        MemoryNoteInfo saved = client.SaveMemoryNote(workspace, note);
        MemoryListResult result = client.ListMemoryNotes(workspace);
        return [this, saved = std::move(saved), result = std::move(result)]() {
            memory_notes_ = result.notes;
            selected_memory_note_index_ = -1;
            for (int i = 0; i < static_cast<int>(memory_notes_.size()); ++i) {
                if (memory_notes_[i].id == saved.id) {
                    selected_memory_note_index_ = i;
                    HydrateMemoryEditor(&memory_notes_[i], i);
                    break;
                }
            }
            status_ = "Saved memory note: " + saved.title + ".";
            PushToast("Memory saved", saved.title, "success");
        };
    });
}

void AegisChatApp::DeleteSelectedMemoryNote()
{
    if (selected_memory_note_index_ < 0 || selected_memory_note_index_ >= static_cast<int>(memory_notes_.size())) {
        status_ = "Select a memory note to delete.";
        return;
    }

    const MemoryNoteInfo note = memory_notes_[selected_memory_note_index_];
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    AegisClient client = client_;
    StartTask("Deleting memory note...", [this, client, workspace, note]() mutable {
        client.DeleteMemoryNote(workspace, note.id);
        MemoryListResult result = client.ListMemoryNotes(workspace);
        return [this, note, result = std::move(result)]() {
            memory_notes_ = result.notes;
            selected_memory_note_index_ = -1;
            HydrateMemoryEditor(nullptr, -1);
            status_ = "Deleted memory note: " + note.title + ".";
            PushToast("Memory deleted", note.title, "success");
        };
    });
}

void AegisChatApp::RefreshValidationProfile()
{
    AegisClient client = client_;
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    StartTask("Loading validation profile...", [this, client, workspace]() mutable {
        ValidationProfileInfo profile = client.GetValidationProfile(workspace);
        return [this, profile = std::move(profile)]() {
            validation_profile_ = profile;
            has_validation_profile_snapshot_ = true;
            if (profile.has_profile) {
                SetBuffer(validation_command_buffer_, profile.profile.command);
                SetBuffer(validation_label_buffer_, profile.profile.label);
                SetBuffer(validation_notes_buffer_, profile.profile.notes);
            }
            if (!profile.workspace_root.empty()) {
                workspace_root_ = profile.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            status_ = profile.has_profile
                ? "Loaded validation profile: " + profile.profile.command
                : "Loaded validation suggestions for this workspace.";
        };
    });
}

void AegisChatApp::SaveValidationProfile(bool clear_profile)
{
    AegisClient client = client_;
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    const std::string command = clear_profile ? "" : BufferString(validation_command_buffer_.data());
    const std::string label = clear_profile ? "" : BufferString(validation_label_buffer_.data());
    const std::string notes = clear_profile ? "" : BufferString(validation_notes_buffer_.data());

    StartTask(clear_profile ? "Clearing validation profile..." : "Saving validation profile...", [this, client, workspace, command, label, notes, clear_profile]() mutable {
        ValidationProfileInfo profile = client.SaveValidationProfile(workspace, command, label, notes);
        return [this, profile = std::move(profile), clear_profile]() {
            validation_profile_ = profile;
            has_validation_profile_snapshot_ = true;
            if (clear_profile || !profile.has_profile) {
                SetBuffer(validation_command_buffer_, "");
                SetBuffer(validation_label_buffer_, "");
                SetBuffer(validation_notes_buffer_, "");
            } else {
                SetBuffer(validation_command_buffer_, profile.profile.command);
                SetBuffer(validation_label_buffer_, profile.profile.label);
                SetBuffer(validation_notes_buffer_, profile.profile.notes);
            }
            status_ = clear_profile ? "Validation profile cleared." : "Validation profile saved.";
        };
    });
}

void AegisChatApp::StartCodingRoute(const std::string& route)
{
    const std::string composer_prompt = Trim(std::string(message_buffer_.data()));
    const std::string goal = composer_prompt.empty()
        ? "Inspect this workspace, identify the most useful next coding step, and make a focused improvement."
        : composer_prompt;

    std::string title = "general coding";
    std::string guidance =
        "Use the general coding route. Inspect the workspace first, keep edits focused, explain tradeoffs, and validate with the saved validation profile when possible.";

    if (route == "web") {
        title = "web app";
        guidance = "Use the Web App route. Prioritize frontend/backend architecture, responsive UI, accessibility, API contracts, state management, build scripts, browser testing, and deployment readiness.";
        mode_ = "develop";
    } else if (route == "mobile") {
        title = "mobile app";
        guidance = "Use the Mobile App route. Identify whether the project is React Native, Flutter, Swift, Kotlin, or another stack; prioritize device layouts, navigation, permissions, offline behavior, performance, and store-ready validation.";
        mode_ = "develop";
    } else if (route == "desktop") {
        title = "desktop app";
        guidance = "Use the Desktop App route. Prioritize native-feeling UX, windowing, DPI scaling, local files, installers, updates, crash handling, logs, and platform conventions.";
        mode_ = "develop";
    } else if (route == "macos") {
        title = "macOS app";
        guidance = "Use the macOS route. Prioritize SwiftUI/AppKit patterns, sandboxing, entitlements, notarization, app bundle structure, keyboard shortcuts, and macOS design conventions.";
        mode_ = "develop";
    } else if (route == "linux") {
        title = "Linux app";
        guidance = "Use the Linux route. Prioritize packages, services, shell scripts, permissions, systemd, distro differences, logs, CLI ergonomics, and reproducible validation commands.";
        mode_ = "develop";
    } else if (route == "windows") {
        title = "Windows app";
        guidance = "Use the Windows route. Prioritize Win32/.NET/C++ conventions, DPI, filesystem paths, installers, services, registry safety, Visual Studio builds, PowerShell validation, and signed release readiness.";
        mode_ = "develop";
    } else if (route == "kernel") {
        title = "kernel/system";
        guidance = "Use the Kernel/System route. Treat this as high risk: start with design, review, threat/safety notes, reproducible build steps, and validation. Avoid destructive commands and do not change boot, driver, firmware, or privileged system behavior without explicit user confirmation.";
        mode_ = "review";
    } else if (route == "game") {
        title = "game/tooling";
        guidance = "Use the Game/Tooling route. Prioritize engine structure, assets, frame pacing, input, editor tooling, save data, rendering checks, and playable verification.";
        mode_ = "develop";
    } else if (route == "data") {
        title = "data/automation";
        guidance = "Use the Data/Automation route. Prioritize parsers, repeatable scripts, schemas, validation, reports, task automation, reproducible outputs, and safe handling of local files.";
        mode_ = "develop";
    } else if (route == "tests") {
        title = "test generation";
        guidance = "Use the Test Generation route. Inspect the detected project stack, identify missing or weak unit/integration/UI tests, add practical tests when the path is clear, and update the validation profile with the best repeatable command.";
        mode_ = "develop";
    }

    run_validation_ = true;
    status_ = "Started " + title + " coding route.";

    const std::vector<ValidationSuggestionInfo> suggestions = BuildProjectValidationSuggestions(files_);
    const std::string validation_context = BuildValidationSuggestionContext(suggestions);

    std::ostringstream prompt;
    prompt << guidance << "\n\n"
           << "User goal: " << goal << "\n\n"
           << (validation_context.empty() ? "" : validation_context + "\n")
           << "Use the active workspace. Make practical changes when the path is clear, keep scope tight, and report validation results.";
    SubmitMessage(prompt.str());
}

MediaGenerationOptions AegisChatApp::BuildMediaGenerationOptionsFromUi() const
{
    MediaGenerationOptions options;
    options.theme_color = BufferString(media_theme_buffer_.data());
    options.aspect_ratio = BufferString(media_aspect_ratio_buffer_.data());
    options.style = BufferString(media_style_buffer_.data());
    options.width = std::clamp(media_width_, 256, 4096);
    options.height = std::clamp(media_height_, 256, 4096);
    options.duration_seconds = std::clamp(static_cast<double>(media_duration_seconds_), 0.5, 120.0);
    options.fps = std::clamp(media_fps_, 1, 60);
    options.output_formats = SplitCommaList(BufferString(media_output_formats_buffer_.data()));
    if (options.aspect_ratio.empty()) {
        options.aspect_ratio = "16:9";
    }
    if (options.style.empty()) {
        options.style = "premium native desktop product";
    }
    return options;
}

void AegisChatApp::CreateMediaJob(const std::string& kind, const std::string& prompt, const std::string& feedback)
{
    const std::string final_prompt = Trim(prompt).empty()
        ? "Create a premium Aegis AI creative asset with a polished futuristic product style."
        : Trim(prompt);
    const std::string final_feedback = Trim(feedback);
    const std::string previous = final_feedback.empty() ? "" : last_media_job_id_;
    const MediaGenerationOptions options = BuildMediaGenerationOptionsFromUi();

    AegisClient client = client_;
    StartTask("Creating " + kind + " studio package...", [this, client, kind, final_prompt, final_feedback, previous, options]() mutable {
        MediaJobSummary job = client.CreateMediaJob(kind, final_prompt, final_feedback, previous, options);
        return [this, job = std::move(job)]() {
            last_media_job_id_ = job.id;
            last_media_kind_ = job.kind;
            selected_media_job_ = job;
            has_selected_media_job_ = true;
            selected_media_job_index_ = 0;
            selected_media_asset_index_ = BestCreativePreviewIndex(job.assets);
            media_jobs_.insert(media_jobs_.begin(), job);
            history_.push_back({"assistant", job.message, NowTimeLabel(), "Creative Studio / " + job.kind});
            SaveConversationSnapshot();
            status_ = "Creative Studio job ready: " + job.id;
        };
    });
}

void AegisChatApp::RefreshMediaJobs()
{
    AegisClient client = client_;
    StartTask("Loading Creative Studio jobs...", [this, client]() mutable {
        std::vector<MediaJobSummary> jobs = client.ListMediaJobs(60);
        return [this, jobs = std::move(jobs)]() {
            ClearCreativeTextureCache();
            media_jobs_ = jobs;
            if (media_jobs_.empty()) {
                has_selected_media_job_ = false;
                selected_media_job_index_ = -1;
                status_ = "No Creative Studio jobs found yet.";
                return;
            }
            selected_media_job_index_ = 0;
            selected_media_job_ = media_jobs_.front();
            has_selected_media_job_ = true;
            selected_media_asset_index_ = BestCreativePreviewIndex(selected_media_job_.assets);
            last_media_job_id_ = selected_media_job_.id;
            last_media_kind_ = selected_media_job_.kind;
            status_ = "Loaded " + std::to_string(media_jobs_.size()) + " Creative Studio job(s).";
        };
    });
}

void AegisChatApp::LoadMediaJob(const std::string& job_id, int index)
{
    if (Trim(job_id).empty()) {
        return;
    }

    AegisClient client = client_;
    StartTask("Loading Creative Studio job...", [this, client, job_id, index]() mutable {
        MediaJobSummary job = client.GetMediaJob(job_id);
        return [this, job = std::move(job), index]() {
            selected_media_job_ = job;
            has_selected_media_job_ = true;
            selected_media_job_index_ = index;
            selected_media_asset_index_ = BestCreativePreviewIndex(job.assets);
            last_media_job_id_ = job.id;
            last_media_kind_ = job.kind;
            if (index >= 0 && index < static_cast<int>(media_jobs_.size())) {
                media_jobs_[index] = job;
            }
            status_ = "Loaded Creative Studio job: " + job.id;
        };
    });
}

const CreativePreviewTexture* AegisChatApp::GetCreativePreviewTexture(const MediaAssetInfo& asset)
{
    if (asset.path.empty() || !IsRasterCreativePreviewFormat(asset.format)) {
        return nullptr;
    }

    CreativePreviewTexture& texture = creative_texture_cache_[asset.path];
    if (!texture.attempted) {
        texture.attempted = true;
        void* view = nullptr;
        int width = 0;
        int height = 0;
        std::string error;
        if (LoadTextureFromImageFile(std::filesystem::path(Utf8ToWide(asset.path)), &view, &width, &height, &error)) {
            texture.shader_resource_view = view;
            texture.width = width;
            texture.height = height;
            texture.error.clear();
        } else {
            texture.error = error.empty() ? "Preview could not be loaded." : error;
        }
    }

    return &texture;
}

void AegisChatApp::ClearCreativeTextureCache()
{
    for (auto& entry : creative_texture_cache_) {
        if (entry.second.shader_resource_view != nullptr) {
            ReleaseTextureResource(entry.second.shader_resource_view);
            entry.second.shader_resource_view = nullptr;
        }
    }
    creative_texture_cache_.clear();
}

void AegisChatApp::OpenWorkspaceFile(const WorkspaceFile& file, int index)
{
    if (file.kind != "text") {
        status_ = "Only text files can be previewed here.";
        return;
    }

    AegisClient client = client_;
    const std::string workspace = workspace_root_;
    StartTask("Opening " + file.path + "...", [this, client, workspace, file, index]() mutable {
        FileContent content = client.ReadFile(workspace, file.path);
        return [this, content = std::move(content), index]() {
            selected_file_ = content;
            has_selected_file_ = true;
            selected_file_index_ = index;
            status_ = "Opened " + selected_file_.path + ".";
        };
    });
}

void AegisChatApp::OpenBackendFolder()
{
    OpenExternalPath(settings_.backend_root);
}

void AegisChatApp::ApplyRuntimeSnapshot(const RuntimeSnapshot& snapshot)
{
    const std::string previous_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    health_ = snapshot.health;
    config_ = snapshot.config;
    models_ = snapshot.model_inventory;
    model_registry_ = snapshot.model_registry;
    has_config_ = true;
    files_ = snapshot.files;
    recent_tasks_ = snapshot.recent_tasks;
    workspace_root_ = snapshot.workspace_root.empty()
        ? (previous_workspace.empty() ? snapshot.config.default_workspace : previous_workspace)
        : snapshot.workspace_root;
    config_.default_workspace = workspace_root_;
    mode_ = config_.default_mode.empty() ? mode_ : config_.default_mode;
    run_validation_ = config_.auto_run_validation;
    HydrateConfigBuffers();
}

void AegisChatApp::HydrateConfigBuffers()
{
    SetBuffer(assistant_name_buffer_, config_.assistant_name);
    SetBuffer(assistant_mission_buffer_, config_.assistant_mission);
    SetBuffer(workspace_buffer_, workspace_root_.empty() ? config_.default_workspace : workspace_root_);
    SetBuffer(model_api_buffer_, config_.model_api);
    SetBuffer(model_endpoint_buffer_, config_.model_endpoint);
    SetBuffer(model_name_buffer_, config_.model_name);
    SetBuffer(command_allowlist_buffer_, config_.command_allowlist);
}

void AegisChatApp::HydrateDesktopBuffers()
{
    SetBuffer(api_base_buffer_, settings_.api_base_url);
    SetBuffer(backend_root_buffer_, WideToUtf8(settings_.backend_root.wstring()));
    SetBuffer(backend_script_buffer_, settings_.backend_start_script);
}

AppConfig AegisChatApp::BuildConfigFromBuffers() const
{
    AppConfig next = config_;
    next.assistant_name = BufferString(assistant_name_buffer_.data());
    next.assistant_mission = BufferString(assistant_mission_buffer_.data());
    next.default_mode = mode_;
    next.default_workspace = BufferString(workspace_buffer_.data());
    next.model_api = BufferString(model_api_buffer_.data());
    next.model_endpoint = BufferString(model_endpoint_buffer_.data());
    next.model_name = BufferString(model_name_buffer_.data());
    next.command_allowlist = BufferString(command_allowlist_buffer_.data());
    next.command_timeout_seconds = std::max(5, std::min(3600, config_.command_timeout_seconds));
    next.auto_run_validation = run_validation_;
    return next;
}

DesktopSettings AegisChatApp::BuildDesktopSettingsFromBuffers() const
{
    DesktopSettings next = settings_;
    next.api_base_url = BufferString(api_base_buffer_.data());
    while (!next.api_base_url.empty() && next.api_base_url.back() == '/') {
        next.api_base_url.pop_back();
    }
    next.backend_root = std::filesystem::path(Utf8ToWide(BufferString(backend_root_buffer_.data())));
    next.backend_start_script = BufferString(backend_script_buffer_.data());
    next.max_files = std::max(20, std::min(500, next.max_files));
    return next;
}

void AegisChatApp::RenderTopBar()
{
    ImGui::BeginChild("topbar", ImVec2(0, 84.0f), false);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const ImVec2 top_origin = ImGui::GetWindowPos();
    const ImVec2 top_size = ImGui::GetWindowSize();
    draw->AddRectFilledMultiColor(
        top_origin,
        ImVec2(top_origin.x + top_size.x, top_origin.y + top_size.y),
        Color(255, 255, 255, 0.018f),
        Color(255, 255, 255, 0.010f),
        Color(0, 0, 0, 0.0f),
        Color(0, 0, 0, 0.0f));
    draw->AddLine(ImVec2(top_origin.x + 24.0f, top_origin.y + top_size.y - 1.0f), ImVec2(top_origin.x + top_size.x - 24.0f, top_origin.y + top_size.y - 1.0f), Color(255, 255, 255, 0.055f), 1.0f);

    ImGui::SetCursorPos(ImVec2(32.0f, 19.0f));
    TextColor("Aegis AI Chat", Rgba(246, 248, 251));
    ImGui::SameLine();
    ImGui::SetCursorPosY(ImGui::GetCursorPosY() - 1.0f);
    const ImVec2 badge_pos = ImGui::GetCursorScreenPos();
    draw->AddRectFilled(badge_pos, ImVec2(badge_pos.x + 45.0f, badge_pos.y + 20.0f), Color(13, 93, 55, 0.92f), 10.0f);
    draw->AddRect(badge_pos, ImVec2(badge_pos.x + 45.0f, badge_pos.y + 20.0f), Color(111, 255, 173, 0.22f + Pulse(2.4f) * 0.18f), 10.0f);
    DrawBitmapIcon(draw, IconGlyph::Bolt, ImVec2(badge_pos.x + 7.0f, badge_pos.y + 5.0f), 10.0f, Color(111, 255, 173));
    draw->AddText(ImVec2(badge_pos.x + 20.0f, badge_pos.y + 3.0f), Color(111, 255, 173), "Pro");
    ImGui::Dummy(ImVec2(48.0f, 20.0f));

    ImGui::SetCursorPos(ImVec2(32.0f, 48.0f));
    TextMuted("Powered by advanced AI models for intelligent conversations");

    const float right = ImGui::GetWindowWidth() - 32.0f;
    const float y = 24.0f;
    ImGui::SetCursorPos(ImVec2(std::max(300.0f, right - 524.0f), y));
    if (IconOnlyButton("command_palette_button", IconGlyph::Search, ImVec2(42.0f, 38.0f), Rgba(8, 13, 20, 0.0f), Rgba(25, 35, 47), Rgba(213, 220, 228))) {
        command_palette_buffer_.fill('\0');
        ImGui::OpenPopup("Aegis Command Palette");
        command_palette_focus_ = true;
    }
    ImGui::SameLine(0.0f, 12.0f);
    if (IconOnlyButton("creative_library_button", IconGlyph::Image, ImVec2(42.0f, 38.0f), Rgba(8, 13, 20, 0.0f), Rgba(25, 35, 47), Rgba(213, 220, 228))) {
        ImGui::OpenPopup("Aegis Creative Studio");
        RefreshMediaJobs();
    }
    ImGui::SameLine(0.0f, 12.0f);
    if (IconOnlyButton("roadmap_button", IconGlyph::Document, ImVec2(42.0f, 38.0f), Rgba(8, 13, 20, 0.0f), Rgba(25, 35, 47), Rgba(213, 220, 228))) {
        ImGui::OpenPopup("Aegis Build Queue");
        status_ = "Opened the Aegis build queue and master roadmap.";
    }
    ImGui::SameLine(0.0f, 12.0f);
    const std::string model_label = config_.model_name.empty() ? "Local Model" : Shorten(config_.model_name, 18);
    if (IconTextButton("model_picker", IconGlyph::Globe, model_label.c_str(), ImVec2(136.0f, 38.0f), Rgba(16, 23, 32), Rgba(25, 35, 47), Rgba(241, 245, 249))) {
        ImGui::OpenPopup("Aegis Model Stack");
        status_ = "Loaded model stack for " + model_label + ".";
    }
    ImGui::SameLine(0.0f, 14.0f);
    if (IconOnlyButton("settings_button", IconGlyph::Sliders, ImVec2(42.0f, 38.0f), Rgba(8, 13, 20, 0.0f), Rgba(25, 35, 47), Rgba(213, 220, 228))) {
        ImGui::OpenPopup("Aegis Settings");
    }
    ImGui::SameLine(0.0f, 28.0f);
    const ImVec2 online_pos = ImGui::GetCursorScreenPos();
    const bool online = health_.engine_ready && health_.model_ready;
    draw->AddCircleFilled(ImVec2(online_pos.x + 8.0f, online_pos.y + 18.0f), online ? 7.0f + Pulse(2.8f) * 2.0f : 5.0f, online ? Color(38, 221, 123, 0.14f) : Color(239, 68, 68, 0.14f));
    draw->AddCircleFilled(ImVec2(online_pos.x + 8.0f, online_pos.y + 18.0f), 4.0f, online ? Color(38, 221, 123) : Color(239, 68, 68));
    draw->AddText(ImVec2(online_pos.x + 20.0f, online_pos.y + 10.0f), online ? Color(38, 221, 123) : Color(239, 115, 115), online ? "AI Online" : "AI Offline");
    ImGui::Dummy(ImVec2(118.0f, 38.0f));

    if (!status_.empty() || busy_) {
        ImGui::SetCursorPos(ImVec2(32.0f, 66.0f));
        ImGui::PushStyleColor(ImGuiCol_Text, Rgba(129, 140, 153));
        ImGui::TextUnformatted(busy_ ? busy_label_.c_str() : Shorten(status_, 128).c_str());
        ImGui::PopStyleColor();
    }
    ImGui::EndChild();
}

void AegisChatApp::RenderRuntimeBanner()
{
    const std::string lowered_status = Lower(status_);
    const bool status_problem =
        lowered_status.find("offline") != std::string::npos ||
        lowered_status.find("failed") != std::string::npos ||
        lowered_status.find("error") != std::string::npos ||
        lowered_status.find("could not") != std::string::npos ||
        lowered_status.find("timed out") != std::string::npos;
    const bool backend_problem = !health_.engine_ready;
    const bool model_problem = !health_.model_ready;

    if (!status_problem && !backend_problem && !model_problem) {
        return;
    }

    const bool severe = status_problem || backend_problem;
    const ImVec4 accent = severe ? Rgba(248, 113, 113) : Rgba(205, 154, 82);
    const std::string title = severe ? "Runtime Needs Attention" : "Model Needs Attention";
    std::string detail;

    if (status_problem && !status_.empty()) {
        detail = status_;
    } else if (backend_problem) {
        detail = "The Aegis backend is not reporting ready. Chat, tools, workspace indexing, and media jobs may be unavailable.";
    } else if (model_problem) {
        detail = health_.model_message.empty()
            ? "The active model is not reporting ready. Open the model stack or settings to check provider configuration."
            : health_.model_message;
    }
    if (detail.empty()) {
        detail = "Runtime state is incomplete. Refresh the backend or open settings to inspect configuration.";
    }

    const float width = ImGui::GetContentRegionAvail().x - 32.0f;
    if (width <= 260.0f) {
        return;
    }

    ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 16.0f);
    const ImVec2 pos = ImGui::GetCursorScreenPos();
    const ImVec2 size(width, 76.0f);
    const ImVec2 max(pos.x + size.x, pos.y + size.y);
    ImDrawList* draw = ImGui::GetWindowDrawList();
    draw->AddRectFilled(ImVec2(pos.x, pos.y + 4.0f), ImVec2(max.x, max.y + 6.0f), Color(0, 0, 0, 0.22f), 10.0f);
    draw->AddRectFilled(pos, max, Color(13, 18, 26, 0.98f), 10.0f);
    draw->AddRect(pos, max, ImGui::GetColorU32(ImVec4(accent.x, accent.y, accent.z, 0.45f)), 10.0f, 0, 1.2f);
    draw->AddRectFilled(ImVec2(pos.x, pos.y), ImVec2(pos.x + 4.0f, max.y), ImGui::GetColorU32(accent), 10.0f);
    draw->AddCircleFilled(ImVec2(pos.x + 36.0f, pos.y + 38.0f), 18.0f, Color(5, 13, 18, 0.96f));
    DrawBitmapIcon(draw, severe ? IconGlyph::Bolt : IconGlyph::Globe, ImVec2(pos.x + 24.0f, pos.y + 26.0f), 24.0f, ImGui::GetColorU32(accent));

    ImGui::InvisibleButton("runtime_banner_surface", size);
    ImGui::SetCursorScreenPos(ImVec2(pos.x + 68.0f, pos.y + 13.0f));
    TextColor(title, accent);
    ImGui::SetCursorScreenPos(ImVec2(pos.x + 68.0f, pos.y + 39.0f));
    TextMuted(Shorten(detail, 128));

    const float button_y = pos.y + 20.0f;
    const float button_w = 112.0f;
    const float right = max.x - 14.0f;
    ImGui::SetCursorScreenPos(ImVec2(right - button_w * 3.0f - 20.0f, button_y));
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Retry", ImVec2(button_w, 34.0f))) {
        RefreshRuntime(true);
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Settings", ImVec2(button_w, 34.0f))) {
        ImGui::OpenPopup("Aegis Settings");
        status_ = "Opened settings.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Models", ImVec2(button_w, 34.0f))) {
        ImGui::OpenPopup("Aegis Model Stack");
        status_ = "Loaded model stack.";
    }
    ImGui::SetCursorScreenPos(ImVec2(pos.x, max.y + 10.0f));
}

void AegisChatApp::RenderLogin()
{
    const ImVec2 size = ImGui::GetWindowSize();
    const ImVec2 origin = ImGui::GetWindowPos();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    const float t = static_cast<float>(ImGui::GetTime());

    draw->AddRectFilled(origin, ImVec2(origin.x + size.x, origin.y + size.y), Color(4, 9, 15), 0.0f);
    draw->AddRectFilledMultiColor(
        origin,
        ImVec2(origin.x + size.x, origin.y + size.y),
        Color(4, 16, 18, 0.95f),
        Color(17, 12, 26, 0.95f),
        Color(2, 8, 14, 1.0f),
        Color(4, 24, 24, 1.0f));

    const float grid_x = std::fmod(t * 8.0f, 96.0f);
    const float grid_y = std::fmod(t * 6.0f, 86.0f);
    for (float x = origin.x + 48.0f - grid_x; x < origin.x + size.x + 96.0f; x += 96.0f) {
        draw->AddLine(ImVec2(x, origin.y + 92.0f), ImVec2(x, origin.y + size.y), Color(198, 222, 210, 0.026f), 1.0f);
    }
    for (float y = origin.y + 116.0f - grid_y; y < origin.y + size.y + 86.0f; y += 86.0f) {
        draw->AddLine(ImVec2(origin.x, y), ImVec2(origin.x + size.x, y), Color(198, 222, 210, 0.020f), 1.0f);
    }

    const ImVec2 scan_a(origin.x + size.x * 0.22f, origin.y + size.y * 0.34f);
    const ImVec2 scan_b(origin.x + size.x * 0.78f, origin.y + size.y * 0.72f);
    for (int i = 0; i < 3; ++i) {
        draw->AddCircle(scan_a, 92.0f + i * 34.0f + Pulse(1.4f, static_cast<float>(i)) * 5.0f, Color(38, 221, 123, 0.055f + i * 0.018f), 96, 1.0f);
        draw->AddCircle(scan_b, 120.0f + i * 38.0f + Pulse(1.1f, static_cast<float>(i) * 0.7f) * 6.0f, Color(75, 125, 255, 0.035f + i * 0.012f), 96, 1.0f);
    }

    const ImVec2 brand_pos(origin.x + 46.0f, origin.y + 42.0f);
    draw->AddRectFilled(brand_pos, ImVec2(brand_pos.x + 54.0f, brand_pos.y + 54.0f), Color(3, 18, 17), 15.0f);
    DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(brand_pos.x + 9.0f, brand_pos.y + 9.0f), 36.0f, Color(38, 221, 123));
    ImGui::SetCursorPos(ImVec2(116.0f, 48.0f));
    TextColor("AEGIS AI CHAT", Rgba(246, 248, 251));
    ImGui::SetCursorPos(ImVec2(116.0f, 74.0f));
    TextMuted("Secure Desktop Session");

    const bool compact_login = size.y < 760.0f || size.x < 940.0f;
    const float card_w = std::min(compact_login ? 480.0f : 540.0f, std::max(390.0f, size.x - 72.0f));
    const float card_h = compact_login ? 438.0f : 504.0f;
    const float card_x = std::max(28.0f, (size.x - card_w) * 0.5f);
    const float card_y = std::max(compact_login ? 44.0f : 74.0f, (size.y - card_h) * 0.5f);
    const ImVec2 card_pos(card_x, card_y);
    ImGui::SetCursorPos(card_pos);
    if (BeginCard("login_card", ImVec2(card_w, card_h), true)) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("WELCOME BACK", Rgba(38, 221, 123));
        ImGui::Dummy(ImVec2(0.0f, 4.0f));
        TextColor("Sign in to Aegis AI Chat", Rgba(246, 248, 251));
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + card_w - 46.0f);
        TextMuted("Use your Aegis desktop account to open the native chat workspace. The backend, model status, memory, tools, and file panels load after sign-in.");
        ImGui::PopTextWrapPos();
        ImGui::Dummy(ImVec2(0.0f, 12.0f));

        ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(10, 17, 25));
        ImGui::PushStyleColor(ImGuiCol_FrameBgHovered, Rgba(16, 25, 36));
        ImGui::PushStyleColor(ImGuiCol_FrameBgActive, Rgba(16, 30, 39));
        ImGui::PushStyleColor(ImGuiCol_Border, Rgba(46, 59, 72));
        ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 8.0f);
        ImGui::PushItemWidth(-1.0f);
        ImGui::TextUnformatted("Username");
        ImGui::InputTextWithHint("##login_username", "MercyTheGod", login_user_buffer_.data(), login_user_buffer_.size());
        ImGui::Dummy(ImVec2(0.0f, 4.0f));
        ImGui::TextUnformatted("Password");
        ImGui::InputTextWithHint("##login_password", "Password", login_password_buffer_.data(), login_password_buffer_.size(), ImGuiInputTextFlags_Password);
        ImGui::PopItemWidth();
        ImGui::PopStyleVar(2);
        ImGui::PopStyleColor(4);

        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        ImGui::Checkbox("Remember this account on this machine", &remember_me_);
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        if (!login_status_.empty()) {
            const bool error_state =
                Lower(login_status_).find("enter") != std::string::npos ||
                Lower(login_status_).find("failed") != std::string::npos ||
                Lower(login_status_).find("could not") != std::string::npos;
            ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + card_w - 46.0f);
            TextColor(login_status_, error_state ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
            ImGui::PopTextWrapPos();
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
        }

        if (IconTextButton("login_sign_in", IconGlyph::Shield, "Sign In", ImVec2(-1.0f, compact_login ? 40.0f : 48.0f), Rgba(20, 175, 88), Rgba(34, 197, 94), Rgba(255, 255, 255)) ||
            (ImGui::IsKeyPressed(ImGuiKey_Enter) && ImGui::IsWindowFocused(ImGuiFocusedFlags_RootAndChildWindows))) {
            AttemptLogin(false);
        }

        if (!compact_login) {
            ImGui::Dummy(ImVec2(0.0f, 7.0f));
            if (IconTextButton("login_demo", IconGlyph::Sparkle, "Continue In Demo Mode", ImVec2(-1.0f, 42.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                AttemptLogin(true);
            }
        }
    }
    EndCard();

    ImGui::SetCursorPos(ImVec2(48.0f, size.y - 50.0f));
    TextMuted("Aegis Automation Suite");
}

void AegisChatApp::RenderSetupLoading()
{
    const ImVec2 size = ImGui::GetWindowSize();
    const auto now = std::chrono::steady_clock::now();
    const float elapsed = setup_started_.time_since_epoch().count() == 0
        ? 0.0f
        : std::chrono::duration<float>(now - setup_started_).count();

    float progress = EaseOutCubic(elapsed / 2.55f);
    if (busy_ && elapsed < 4.4f) {
        progress = std::min(progress, 0.86f);
    } else {
        progress = std::max(progress, 0.94f);
    }

    const bool compact = size.y < 690.0f || size.x < 900.0f;
    const float card_w = std::min(compact ? 560.0f : 660.0f, std::max(420.0f, size.x - 80.0f));
    const float card_h = compact ? 480.0f : 560.0f;
    ImGui::SetCursorPos(ImVec2(
        std::max(28.0f, (size.x - card_w) * 0.5f),
        std::max(46.0f, (size.y - card_h) * 0.5f)));

    if (BeginCard("setup_loading_card", ImVec2(card_w, card_h), true)) {
        ImDrawList* draw = ImGui::GetWindowDrawList();
        const ImVec2 win_pos = ImGui::GetWindowPos();
        const ImVec2 win_size = ImGui::GetWindowSize();
        const float center_x = win_pos.x + win_size.x * 0.5f;
        const float pulse = 0.68f + Pulse(2.6f) * 0.32f;

        draw->AddRectFilledMultiColor(
            win_pos,
            ImVec2(win_pos.x + win_size.x, win_pos.y + (compact ? 92.0f : 112.0f)),
            Color(38, 221, 123, 0.075f * pulse),
            Color(205, 154, 82, 0.045f * pulse),
            Color(38, 221, 123, 0.0f),
            Color(38, 221, 123, 0.0f));

        const float spinner_y = win_pos.y + (compact ? 58.0f : 72.0f);
        DrawSpinner(draw, ImVec2(center_x, spinner_y), compact ? 30.0f : 36.0f, 3.4f, Color(255, 255, 255, 0.10f), Color(38, 221, 123, 0.96f));
        draw->AddRectFilled(ImVec2(center_x - 18.0f, spinner_y - 18.0f), ImVec2(center_x + 18.0f, spinner_y + 18.0f), Color(4, 18, 17, 0.90f), 10.0f);
        DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(center_x - 12.0f, spinner_y - 12.0f), 24.0f, Color(38, 221, 123));

        auto centered_text = [](const char* text, ImVec4 color) {
            const float text_width = ImGui::CalcTextSize(text).x;
            ImGui::SetCursorPosX(std::max(0.0f, (ImGui::GetWindowWidth() - text_width) * 0.5f));
            TextColor(text, color);
        };

        ImGui::SetCursorPosY(compact ? 98.0f : 122.0f);
        centered_text("AEGIS WORKSPACE", Rgba(38, 221, 123));
        ImGui::Dummy(ImVec2(0.0f, 2.0f));
        centered_text("Preparing your dashboard", Rgba(246, 248, 251));
        ImGui::Dummy(ImVec2(0.0f, compact ? 4.0f : 8.0f));

        const std::string active_status = busy_
            ? (busy_label_.empty() ? "Connecting services..." : busy_label_)
            : "Finishing visual setup...";
        ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + win_size.x - 56.0f);
        const float status_width = ImGui::CalcTextSize(active_status.c_str()).x;
        ImGui::SetCursorPosX(std::max(24.0f, (ImGui::GetWindowWidth() - std::min(status_width, win_size.x - 64.0f)) * 0.5f));
        TextMuted(active_status);
        ImGui::PopTextWrapPos();
        ImGui::Dummy(ImVec2(0.0f, compact ? 8.0f : 14.0f));

        DrawProgress(progress, ImVec2(ImGui::GetContentRegionAvail().x, 8.0f), true);
        ImGui::Dummy(ImVec2(0.0f, compact ? 10.0f : 16.0f));

        struct SetupStep {
            const char* title;
            const char* detail;
            float threshold;
        };
        const SetupStep steps[] = {
            {"Session", "Profile accepted", 0.10f},
            {"Backend", "Runtime handshake", 0.34f},
            {"Models", "Provider status", 0.60f},
            {"Dashboard", "Panels and workspace", 0.84f},
        };

        for (int i = 0; i < 4; ++i) {
            const bool complete = progress >= steps[i].threshold;
            const bool current = !complete && (i == 0 || progress >= steps[i - 1].threshold);
            const ImVec2 row = ImGui::GetCursorScreenPos();
            const ImVec2 row_size(ImGui::GetContentRegionAvail().x, compact ? 39.0f : 46.0f);
            const ImU32 row_color = current ? Color(25, 35, 45, 0.90f) : Color(0, 0, 0, 0.0f);
            draw->AddRectFilled(row, ImVec2(row.x + row_size.x, row.y + row_size.y), row_color, 9.0f);
            draw->AddRect(row, ImVec2(row.x + row_size.x, row.y + row_size.y), current ? Color(255, 255, 255, 0.10f) : Color(255, 255, 255, 0.040f), 9.0f);

            const ImU32 mark = complete ? Color(38, 221, 123) : (current ? Color(205, 154, 82) : Color(88, 99, 113));
            draw->AddRectFilled(ImVec2(row.x + 14.0f, row.y + (compact ? 10.0f : 13.0f)), ImVec2(row.x + 34.0f, row.y + (compact ? 30.0f : 33.0f)), mark, 5.0f);
            if (current) {
                draw->AddRect(ImVec2(row.x + 10.0f, row.y + (compact ? 6.0f : 9.0f)), ImVec2(row.x + 38.0f, row.y + (compact ? 34.0f : 37.0f)), Color(205, 154, 82, 0.18f + Pulse(3.0f) * 0.10f), 8.0f);
            }
            draw->AddText(ImVec2(row.x + 50.0f, row.y + (compact ? 5.0f : 7.0f)), complete ? Color(244, 248, 246) : Color(207, 216, 226), steps[i].title);
            draw->AddText(ImVec2(row.x + 50.0f, row.y + (compact ? 22.0f : 25.0f)), Color(126, 138, 151), steps[i].detail);
            const char* state = complete ? "Ready" : (current ? "Running" : "Queued");
            draw->AddText(ImVec2(row.x + row_size.x - 78.0f, row.y + (compact ? 11.0f : 15.0f)), complete ? Color(38, 221, 123) : (current ? Color(205, 154, 82) : Color(117, 128, 143)), state);
            ImGui::Dummy(row_size);
            ImGui::Dummy(ImVec2(0.0f, compact ? 3.0f : 5.0f));
        }
    }
    EndCard();
}

void AegisChatApp::RenderLeftPanel()
{
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(6, 12, 19, 0.98f));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(38, 49, 62, 0.75f));
    ImGui::BeginChild("left_panel", ImVec2(0, 0), true, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor(2);

    ImDrawList* draw = ImGui::GetWindowDrawList();
    ImVec2 logo_pos = ImGui::GetCursorScreenPos();
    logo_pos.x += 8.0f;
    logo_pos.y += 10.0f;
    draw->AddRectFilled(logo_pos, ImVec2(logo_pos.x + 44.0f, logo_pos.y + 44.0f), Color(3, 18, 17), 13.0f);
    DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(logo_pos.x + 7.0f, logo_pos.y + 7.0f), 30.0f, Color(38, 221, 123));
    ImGui::SetCursorPos(ImVec2(70.0f, 20.0f));
    TextColor("Aegis AI", Rgba(246, 248, 251));
    ImGui::SetCursorPos(ImVec2(70.0f, 43.0f));
    TextMuted("Your AI Assistant");

    ImGui::SetCursorPosY(94.0f);
    if (IconTextButton("new_chat", IconGlyph::Plus, "New Chat", ImVec2(-1.0f, 42.0f), Rgba(20, 175, 88), Rgba(34, 197, 94), Rgba(255, 255, 255))) {
        StartNewChat();
    }
    ImGui::Separator();
    ImGui::Dummy(ImVec2(0.0f, 6.0f));

    if (NavButton("nav_chat", IconGlyph::Chat, "Chat", mode_ == "chat" || mode_ == "build")) {
        mode_ = "chat";
    }
    if (NavButton("nav_explore", IconGlyph::Explore, "Explore", mode_ == "review")) {
        mode_ = "review";
    }
    if (NavButton("nav_agents", IconGlyph::Agents, "Agents", mode_ == "develop")) {
        mode_ = "develop";
    }
    if (NavButton("nav_documents", IconGlyph::Documents, "Documents", false)) {
        status_ = "Document workflows are planned for the model/tool expansion.";
    }
    if (NavButton("nav_tools", IconGlyph::Tools, "Tools", false)) {
        ImGui::OpenPopup("Aegis Settings");
    }
    if (NavButton("nav_history", IconGlyph::History, "History", false)) {
        RefreshRuntime(false);
    }

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    ImGui::TextUnformatted("Recent Chats");
    ImGui::SameLine(ImGui::GetContentRegionAvail().x + ImGui::GetCursorPosX() - 24.0f);
    DrawBitmapIcon(draw, IconGlyph::Search, ImGui::GetCursorScreenPos(), 14.0f, Color(151, 160, 171));
    ImGui::Dummy(ImVec2(16.0f, 16.0f));
    ImGui::Dummy(ImVec2(0.0f, 4.0f));

    int recent_index = 0;
    for (const TaskSummary& task : recent_tasks_) {
        if (recent_index >= 7) {
            break;
        }
        const std::string label = Shorten(task.message.empty() ? "Untitled task" : task.message, 30);
        const std::string time = task.finished_at.empty() ? task.created_at : task.finished_at;
        const bool active = recent_index == 0;
        const ImVec2 row_pos = ImGui::GetCursorScreenPos();
        const ImVec2 row_size(ImGui::GetContentRegionAvail().x, 34.0f);
        ImGui::InvisibleButton(("recent_" + std::to_string(recent_index)).c_str(), row_size);
        draw->AddRectFilled(row_pos, ImVec2(row_pos.x + row_size.x, row_pos.y + row_size.y), active ? Color(15, 69, 47, 0.78f) : Color(0, 0, 0, 0), 7.0f);
        if (active) {
            draw->AddRectFilled(ImVec2(row_pos.x, row_pos.y + 6.0f), ImVec2(row_pos.x + 3.0f, row_pos.y + row_size.y - 6.0f), Color(38, 221, 123), 2.0f);
        }
        DrawBitmapIcon(draw, recent_index % 2 == 0 ? IconGlyph::Chat : IconGlyph::Mail, ImVec2(row_pos.x + 13.0f, row_pos.y + 10.0f), 13.0f, active ? Color(38, 221, 123) : Color(154, 164, 176));
        draw->AddText(ImVec2(row_pos.x + 34.0f, row_pos.y + 8.0f), active ? Color(38, 221, 123) : Color(209, 216, 224), label.c_str());
        draw->AddText(ImVec2(row_pos.x + row_size.x - 48.0f, row_pos.y + 8.0f), Color(126, 136, 149), Shorten(time, 6).c_str());
        ++recent_index;
    }
    if (recent_index == 0) {
        const char* samples[] = {
            "Market analysis today",
            "Explain quantum computing",
            "Python code help",
            "Marketing strategy ideas",
        };
        for (int i = 0; i < 4; ++i) {
            const ImVec2 row_pos = ImGui::GetCursorScreenPos();
            const ImVec2 row_size(ImGui::GetContentRegionAvail().x, 34.0f);
            ImGui::InvisibleButton(("recent_sample_" + std::to_string(i)).c_str(), row_size);
            if (ImGui::IsItemClicked()) {
                SubmitMessage(samples[i]);
            }
            DrawBitmapIcon(draw, i == 0 ? IconGlyph::Chat : IconGlyph::Mail, ImVec2(row_pos.x + 13.0f, row_pos.y + 10.0f), 13.0f, i == 0 ? Color(38, 221, 123) : Color(154, 164, 176));
            draw->AddText(ImVec2(row_pos.x + 34.0f, row_pos.y + 8.0f), i == 0 ? Color(38, 221, 123) : Color(209, 216, 224), samples[i]);
        }
    }

    const float bottom_start = std::max(ImGui::GetCursorPosY() + 12.0f, ImGui::GetWindowHeight() - 282.0f);
    ImGui::SetCursorPosY(bottom_start);
    if (BeginCard("usage_card", ImVec2(0, 152.0f))) {
        ImGui::TextUnformatted("AI Usage This Month");
        ImGui::SameLine(ImGui::GetContentRegionAvail().x - 26.0f);
        TextColor("78%", Rgba(246, 248, 251));
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        DrawProgress(0.78f, ImVec2(ImGui::GetContentRegionAvail().x, 7.0f));
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        TextMuted("3,125 / 4,000 messages used");
        ImGui::Dummy(ImVec2(0.0f, 12.0f));
        if (IconTextButton("upgrade_pro", IconGlyph::Bolt, "Upgrade to Pro", ImVec2(-1.0f, 40.0f), Rgba(25, 32, 41), Rgba(35, 45, 56), Rgba(248, 250, 252))) {
            status_ = "Pro billing is not wired yet.";
        }
    }
    EndCard();

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    if (BeginCard("profile_card", ImVec2(0, 66.0f))) {
        const ImVec2 avatar = ImGui::GetCursorScreenPos();
        draw->AddCircleFilled(ImVec2(avatar.x + 24.0f, avatar.y + 25.0f), 19.0f, Color(74, 222, 128));
        draw->AddText(ImVec2(avatar.x + 14.0f, avatar.y + 17.0f), Color(255, 255, 255), "ME");
        ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 52.0f);
        ImGui::SetCursorPosY(ImGui::GetCursorPosY() + 7.0f);
        ImGui::TextUnformatted("MercyTheGod");
        ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 52.0f);
        TextMuted("mercy@aegisai.com");
    }
    EndCard();
    ImGui::EndChild();
}

void AegisChatApp::RenderChatPanel()
{
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(0, 0, 0, 0));
    ImGui::BeginChild("chat_panel", ImVec2(0, 0), false, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor();
    const std::string active_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string active_api = models_.active_api.empty() ? BufferString(model_api_buffer_.data()) : models_.active_api;
    const std::string active_endpoint = models_.active_endpoint.empty() ? BufferString(model_endpoint_buffer_.data()) : models_.active_endpoint;
    const bool cloud_context_warning = IsCloudModelTarget(active_api, active_endpoint) && (!active_workspace.empty() || !attachments_.empty());
    const float composer_height = 172.0f + (attachments_.empty() ? 0.0f : 58.0f) + (cloud_context_warning ? 46.0f : 0.0f);
    const float footer_height = 30.0f;
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(0, 0, 0, 0));
    ImGui::BeginChild("messages", ImVec2(0, -composer_height - footer_height), false);
    ImGui::PopStyleColor();
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (history_.empty()) {
        const float width = std::min(760.0f, ImGui::GetContentRegionAvail().x - 64.0f);
        ImGui::SetCursorPosX((ImGui::GetContentRegionAvail().x - width) * 0.5f);
        if (BeginCard("empty_state_card", ImVec2(width, 220.0f))) {
            ImGui::Dummy(ImVec2(0.0f, 20.0f));
            TextColor("What are we building?", Rgba(246, 248, 251));
            TextMuted("Pick a starter prompt or type a task below.");
            ImGui::Dummy(ImVec2(0.0f, 12.0f));
            const char* prompts[] = {
                "Help me debug this error",
                "Create a project from scratch in this directory",
                "Review this workspace and find the next move",
                "Refactor this code to be faster"
            };
            for (const char* prompt : prompts) {
                if (IconTextButton(prompt, IconGlyph::Sparkle, prompt, ImVec2(-1.0f, 34.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                    SubmitMessage(prompt);
                }
            }
        }
        EndCard();
    } else {
        for (const ChatMessage& message : history_) {
            RenderMessage(message);
        }
    }

    if (busy_) {
        const float available = ImGui::GetContentRegionAvail().x;
        const float card_width = std::min(620.0f, available * 0.68f);
        ImGui::SetCursorPosX(32.0f);
        if (BeginCard("thinking_message", ImVec2(card_width, 88.0f), true)) {
            ImDrawList* draw = ImGui::GetWindowDrawList();
            const ImVec2 pos = ImGui::GetCursorScreenPos();
            DrawSpinner(draw, ImVec2(pos.x + 24.0f, pos.y + 27.0f), 16.0f, 2.5f, Color(255, 255, 255, 0.09f), Color(38, 221, 123));
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 58.0f);
            TextColor("Aegis is working", Rgba(38, 221, 123));
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 58.0f);
            const std::string label = busy_label_.empty() ? "Preparing the next response" : busy_label_;
            TextMuted(label);
            const float dot_y = pos.y + 58.0f;
            for (int i = 0; i < 3; ++i) {
                const float dot = 0.35f + Pulse(4.0f, static_cast<float>(i) * 0.85f) * 0.65f;
                draw->AddRectFilled(ImVec2(pos.x + 58.0f + i * 13.0f, dot_y), ImVec2(pos.x + 64.0f + i * 13.0f, dot_y + 6.0f), Color(38, 221, 123, dot), 3.0f);
            }
            ImGui::SetCursorPos(ImVec2(ImGui::GetWindowWidth() - 130.0f, 18.0f));
            if (IconTextButton("cancel_response", IconGlyph::Bolt, cancel_response_requested_ ? "Canceling" : "Cancel", ImVec2(108.0f, 34.0f), Rgba(25, 32, 41), Rgba(52, 38, 45), cancel_response_requested_ ? Rgba(205, 154, 82) : Rgba(248, 180, 180))) {
                CancelActiveResponse();
            }
        }
        EndCard();
        ImGui::Dummy(ImVec2(0.0f, 20.0f));
    }

    if (auto_scroll_ && ImGui::GetScrollY() >= ImGui::GetScrollMaxY() - 12.0f) {
        ImGui::SetScrollHereY(1.0f);
    }
    ImGui::EndChild();

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    const float composer_width = ImGui::GetContentRegionAvail().x - 32.0f;
    ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 16.0f);
    if (BeginCard("composer_card", ImVec2(composer_width, composer_height - 10.0f), true)) {
        ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(0, 0, 0, 0));
        ImGui::PushStyleColor(ImGuiCol_Border, Rgba(0, 0, 0, 0));
        ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 0.0f);
        ImGui::InputTextMultiline(
            "##composer",
            message_buffer_.data(),
            message_buffer_.size(),
            ImVec2(-1.0f, 54.0f),
            ImGuiInputTextFlags_AllowTabInput);
        if (Trim(std::string(message_buffer_.data())).empty() && !ImGui::IsItemActive()) {
            const ImVec2 hint = ImGui::GetItemRectMin();
            ImGui::GetWindowDrawList()->AddText(ImVec2(hint.x + 4.0f, hint.y + 6.0f), Color(132, 142, 155), "Message Aegis AI...");
        }
        ImGui::PopStyleVar();
        ImGui::PopStyleColor(2);

        if (cloud_context_warning) {
            const ImVec2 warning_pos = ImGui::GetCursorScreenPos();
            const ImVec2 warning_size(ImGui::GetContentRegionAvail().x, 38.0f);
            ImDrawList* draw = ImGui::GetWindowDrawList();
            draw->AddRectFilled(warning_pos, ImVec2(warning_pos.x + warning_size.x, warning_pos.y + warning_size.y), Color(48, 35, 20, 0.92f), 8.0f);
            draw->AddRect(warning_pos, ImVec2(warning_pos.x + warning_size.x, warning_pos.y + warning_size.y), Color(205, 154, 82, 0.54f), 8.0f);
            DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(warning_pos.x + 12.0f, warning_pos.y + 11.0f), 16.0f, Color(205, 154, 82));
            draw->AddText(ImVec2(warning_pos.x + 38.0f, warning_pos.y + 10.0f), Color(246, 214, 156), "Cloud provider may receive workspace context");
            ImGui::Dummy(warning_size);
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
        }

        if (!attachments_.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
            TextMuted("Attached context");
            ImGui::BeginChild("attachment_tray", ImVec2(0, 42.0f), false, ImGuiWindowFlags_HorizontalScrollbar);
            for (size_t i = 0; i < attachments_.size(); ++i) {
                ImGui::PushID(static_cast<int>(i));
                if (i > 0) {
                    ImGui::SameLine();
                }
                const std::string label = Shorten(attachments_[i].path, 36);
                if (ImGui::SmallButton(("x " + label).c_str())) {
                    RemoveAttachment(i);
                    ImGui::PopID();
                    break;
                }
                ImGui::PopID();
            }
            ImGui::EndChild();
        }

        ImGui::Dummy(ImVec2(0.0f, 2.0f));
        ImGui::Checkbox("Auto Apply", &apply_changes_);
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Low-risk generated changes write immediately; blocked changes stay in preview.");
        }
        ImGui::SameLine(0.0f, 18.0f);
        ImGui::Checkbox("Validate", &run_validation_);
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Run the saved validation command after eligible file writes.");
        }
        if (ImGui::GetWindowWidth() > 780.0f) {
            ImGui::SameLine(0.0f, 18.0f);
            ImGui::SetNextItemWidth(118.0f);
            ImGui::SliderInt("Repairs", &max_repairs_, 0, 3);
            if (ImGui::IsItemHovered()) {
                ImGui::SetTooltip("Automatic validation repair attempts after a failed validation run.");
            }
        }
        if (ImGui::GetWindowWidth() > 1020.0f) {
            ImGui::SameLine(0.0f, 18.0f);
            TextMuted("Workspace: " + Shorten(active_workspace.empty() ? "not selected" : active_workspace, 54));
        }

        ImGui::Dummy(ImVec2(0.0f, 4.0f));
        if (IconOnlyButton("composer_plus", IconGlyph::Plus, ImVec2(42.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(222, 229, 237))) {
            AttachSelectedFile();
        }
        ImGui::SameLine();
        if (IconTextButton("composer_tools", IconGlyph::Tools, "Tools", ImVec2(96.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
            ImGui::OpenPopup("Aegis Settings");
        }
        ImGui::SameLine();
        if (IconTextButton("composer_attach", IconGlyph::Attach, "Attach", ImVec2(108.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
            AttachSelectedFile();
        }
        if (ImGui::GetWindowWidth() > 540.0f) {
            ImGui::SameLine();
            if (IconTextButton("composer_context", IconGlyph::Shield, "Context", ImVec2(116.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                pending_popup_ = "Aegis Context Preview";
                status_ = "Opened context preview.";
            }
        }

        const float send_x = ImGui::GetWindowWidth() - 56.0f;
        ImGui::SameLine(send_x);
        ImGui::BeginDisabled(busy_);
        if (IconOnlyButton("send_message", IconGlyph::Send, ImVec2(40.0f, 40.0f), Rgba(20, 175, 88), Rgba(34, 197, 94), Rgba(255, 255, 255))) {
            workspace_root_ = BufferString(workspace_buffer_.data());
            SubmitMessage();
        }
        ImGui::EndDisabled();
    }
    EndCard();

    ImGui::SetCursorPosX(0.0f);
    ImGui::BeginChild("chat_footer", ImVec2(0, footer_height), false);
    const char* warning = "Aegis AI can make mistakes. Consider checking important information.";
    const float text_width = ImGui::CalcTextSize(warning).x;
    ImGui::SetCursorPosX(std::max(0.0f, (ImGui::GetWindowWidth() - text_width) * 0.5f));
    TextMuted(warning);
    ImGui::EndChild();
    ImGui::EndChild();
}

void AegisChatApp::RenderRightPanel()
{
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(0, 0, 0, 0));
    ImGui::BeginChild("right_panel", ImVec2(0, 0), false, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor();
    ImGui::Dummy(ImVec2(0.0f, 2.0f));

    if (BeginCard("chat_info_card", ImVec2(0, 246.0f))) {
        TextColor("Chat Info", Rgba(246, 248, 251));
        ImGui::Separator();
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        ImGui::Columns(2, "chat_info_columns", false);
        TextMuted("Model");
        TextColor(config_.model_name.empty() ? "Local model" : Shorten(config_.model_name, 18), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Created");
        TextColor(history_.empty() ? "Today" : ("Today, " + history_.front().time_label), Rgba(246, 248, 251));
        ImGui::NextColumn();
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextMuted("Messages");
        TextColor(std::to_string(history_.size()), Rgba(246, 248, 251));
        ImGui::NextColumn();
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextMuted("Tokens Used");
        TextColor(std::to_string(ApproxTokens(history_)), Rgba(246, 248, 251));
        ImGui::Columns(1);
        ImGui::Dummy(ImVec2(0.0f, 18.0f));
        const float action_width = (ImGui::GetContentRegionAvail().x - 8.0f) * 0.5f;
        if (IconTextButton("conversation_library", IconGlyph::History, "Library", ImVec2(action_width, 40.0f), Rgba(15, 23, 32), Rgba(25, 35, 47), Rgba(246, 248, 251))) {
            RefreshConversationLibrary();
            pending_popup_ = "Aegis Conversations";
            status_ = "Opened conversations.";
        }
        ImGui::SameLine();
        if (IconTextButton("export_conversation", IconGlyph::Copy, "Export Chat", ImVec2(-1.0f, 40.0f), Rgba(15, 23, 32), Rgba(25, 35, 47), Rgba(246, 248, 251))) {
            ExportConversationMarkdown();
        }
    }
    EndCard();

    ImGui::Dummy(ImVec2(0.0f, 4.0f));
    if (BeginCard("quick_tools_card", ImVec2(0, 292.0f))) {
        TextColor("Quick Tools", Rgba(246, 248, 251));
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        if (RowButton("quick_web", IconGlyph::Globe, "Web Search", "Search the web for current information")) {
            SubmitMessage("Search the web for the latest reliable information on this topic and summarize it with sources.");
        }
        ImGui::Separator();
        if (RowButton("quick_code", IconGlyph::Code, "Code Interpreter", "Run code and analyze data")) {
            ImGui::OpenPopup("Aegis Coding Routes");
            status_ = "Choose a focused coding route.";
        }
        ImGui::Separator();
        if (RowButton("quick_docs", IconGlyph::Documents, "Document Analyzer", "Analyze and extract insights")) {
            SubmitMessage("Analyze the important documents in this workspace and summarize the actionable insights.");
        }
        ImGui::Separator();
        if (RowButton("quick_image", IconGlyph::Image, "Creative Studio", "Images, video, GIF, PSD, beats")) {
            const std::string composer_prompt = Trim(std::string(message_buffer_.data()));
            const std::string prompt = composer_prompt.empty()
                ? "Create a premium Aegis AI creative asset with a clean dark interface style."
                : composer_prompt;
            const std::string lower_prompt = Lower(prompt);
            const auto has = [&lower_prompt](const char* term) {
                return lower_prompt.find(term) != std::string::npos;
            };
            std::string kind = "image";
            if (has("music") || has("beat") || has("beats") || has("song") || has("audio") ||
                has("instrumental") || has("trap") || has("lofi") || has("lo-fi") ||
                has("melody") || has("drum") || has("bassline")) {
                kind = "music_beat";
            } else if (has("video edit") || has("edit video") || has("editing") || has("timeline") ||
                       has("caption") || has("captions") || has("transition") || has("transitions") ||
                       has("cut ") || has(" cuts") || has("pacing")) {
                kind = "video_edit";
            } else if (has("video") || has("mp4") || has("webm")) {
                kind = "video";
            } else if (has("gif")) {
                kind = "gif";
            } else if (has("animation") || has("animated") || has("motion")) {
                kind = "animation";
            } else if (has("psd") || has("photoshop") || has("template")) {
                kind = "psd_template";
            }
            const bool revision =
                !last_media_job_id_.empty() &&
                !composer_prompt.empty() &&
                (has("revise") ||
                 has("refine") ||
                 has("adjust") ||
                 has("change") ||
                 has("make it") ||
                 has("more ") ||
                 has("less "));
            CreateMediaJob(revision && !last_media_kind_.empty() ? last_media_kind_ : kind, prompt, revision ? prompt : "");
        }
    }
    EndCard();

    ImGui::Dummy(ImVec2(0.0f, 4.0f));
    if (BeginCard("suggested_prompts_card", ImVec2(0, 254.0f))) {
        TextColor("Suggested Prompts", Rgba(246, 248, 251));
        ImGui::SameLine(ImGui::GetWindowWidth() - 34.0f);
        DrawBitmapIcon(ImGui::GetWindowDrawList(), IconGlyph::Regen, ImGui::GetCursorScreenPos(), 16.0f, Color(151, 160, 171));
        ImGui::Dummy(ImVec2(20.0f, 20.0f));
        ImGui::Dummy(ImVec2(0.0f, 8.0f));

        const char* prompts[] = {
            "What are the latest AI developments?",
            "Explain this concept simply",
            "Help me write a professional email",
            "Analyze this data for me",
        };
        for (int i = 0; i < 4; ++i) {
            if (RowButton(("prompt_" + std::to_string(i)).c_str(), IconGlyph::Sparkle, prompts[i], "")) {
                SubmitMessage(prompts[i]);
            }
        }
    }
    EndCard();

    ImGui::Dummy(ImVec2(0.0f, 16.0f));
    if (has_response_ && (!last_response_.changes.empty() || last_response_.has_validation)) {
        if (BeginCard("task_snapshot_card", ImVec2(0, 286.0f))) {
            TextColor("Task Snapshot", Rgba(246, 248, 251));
            ImGui::Separator();
            const bool fully_applied = ResponseChangesFullyApplied(last_response_);
            const bool can_rollback = !last_response_.checkpoint.empty();
            const bool validation_failed = ValidationFailed(last_response_);
            const int applied_count = AppliedChangeCount(last_response_);
            if (last_response_.changes.empty()) {
                TextMuted("No generated file changes in the latest response.");
            } else if (fully_applied) {
                TextMuted(std::to_string(applied_count) + " change(s) already applied to the workspace.");
            } else if (!last_response_.applied.empty()) {
                TextMuted(std::to_string(applied_count) + " applied, " +
                    std::to_string(last_response_.changes.size() - static_cast<size_t>(applied_count)) + " still preview-only.");
            } else {
                TextMuted(std::to_string(last_response_.changes.size()) + " generated change(s) ready to review.");
            }
            if (!last_response_.changes.empty()) {
                ImGui::BeginDisabled(busy_ || fully_applied);
                if (IconTextButton("apply_snapshot_changes", IconGlyph::Bolt, fully_applied ? "Applied" : "Apply Changes", ImVec2(-1.0f, 38.0f), Rgba(20, 175, 88), Rgba(34, 197, 94), Rgba(255, 255, 255))) {
                    ApplyPendingChanges();
                }
                ImGui::EndDisabled();
            }
            if (can_rollback) {
                ImGui::Dummy(ImVec2(0.0f, 6.0f));
                ImGui::BeginDisabled(busy_);
                if (IconTextButton("rollback_snapshot_apply", IconGlyph::Regen, "Rollback Last Apply", ImVec2(-1.0f, 34.0f), Rgba(44, 31, 20), Rgba(126, 74, 28), Rgba(255, 238, 210))) {
                    RollbackLastApply();
                }
                ImGui::EndDisabled();
            }
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            ImGui::BeginDisabled(busy_);
            if (IconTextButton("checkpoint_snapshot_browser", IconGlyph::History, "Checkpoint Browser", ImVec2(-1.0f, 34.0f), Rgba(15, 23, 32), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                RefreshCheckpoints();
                pending_popup_ = "Aegis Checkpoints";
            }
            ImGui::EndDisabled();
            if (last_response_.has_validation) {
                ImGui::Dummy(ImVec2(0.0f, 8.0f));
                TextColor(validation_failed ? "Validation needs repair" : "Validation passed",
                          validation_failed ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
                TextMuted(last_response_.validation.summary.empty() ? "Validation finished." : last_response_.validation.summary);
                if (validation_failed) {
                    ImGui::BeginDisabled(busy_);
                    if (IconTextButton("fix_snapshot_validation", IconGlyph::Bolt, "Fix Validation", ImVec2(-1.0f, 34.0f), Rgba(44, 24, 24), Rgba(97, 39, 39), Rgba(255, 231, 231))) {
                        RepairLastValidationFailure();
                    }
                    ImGui::EndDisabled();
                } else if (!last_response_.repair_attempts.empty()) {
                    TextMuted(std::to_string(last_response_.repair_attempts.size()) + " repair attempt(s) recorded.");
                }
            }
        }
        EndCard();
    }
    ImGui::EndChild();
}

void AegisChatApp::RenderResponseTab()
{
    if (!has_response_) {
        TextMuted("The next response will appear here.");
        return;
    }

    ImGui::TextWrapped("%s", last_response_.reply.c_str());
    if (!last_response_.reply.empty()) {
        if (ImGui::Button("Copy Response")) {
            ImGui::SetClipboardText(last_response_.reply.c_str());
            status_ = "Copied response to clipboard.";
        }
        ImGui::SameLine();
        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Like Response")) {
            RecordFeedback("liked", last_response_.reply, "response_tab; task_id=" + last_response_.task_id);
        }
        ImGui::SameLine();
        if (ImGui::Button("Reject Response")) {
            RecordFeedback("disliked", last_response_.reply, "response_tab; task_id=" + last_response_.task_id);
        }
        ImGui::EndDisabled();
    }
    if (!last_response_.plan.empty()) {
        ImGui::Separator();
        ImGui::TextUnformatted("Plan");
        for (size_t i = 0; i < last_response_.plan.size(); ++i) {
            ImGui::BulletText("%s", last_response_.plan[i].c_str());
        }
    }

    if (!last_response_.warnings.empty()) {
        ImGui::Separator();
        ImGui::TextUnformatted("Warnings");
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.91f, 0.62f, 0.24f, 1.0f));
        for (const std::string& warning : last_response_.warnings) {
            ImGui::BulletText("%s", warning.c_str());
        }
        ImGui::PopStyleColor();
    }

    if (last_response_.has_validation) {
        ImGui::Separator();
        ImGui::TextUnformatted("Validation");
        ImGui::SameLine();
        const bool validation_failed = ValidationFailed(last_response_);
        Pill(validation_failed ? "Failed" : "Passed", validation_failed ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
        ImGui::TextWrapped("%s", last_response_.validation.summary.c_str());
        TextMuted(last_response_.validation.command);
        const std::string validation_output = ValidationCombinedOutput(last_response_.validation);
        const std::string validation_payload =
            "Command: " + last_response_.validation.command + "\n\nSummary: " + last_response_.validation.summary +
            "\n\nOutput:\n" + validation_output;
        ImGui::BeginDisabled(busy_ || !validation_failed);
        if (ImGui::Button("Fix Validation")) {
            RepairLastValidationFailure();
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        ImGui::BeginDisabled(last_response_.validation.command.empty());
        if (ImGui::Button("Copy Command##validation")) {
            ImGui::SetClipboardText(last_response_.validation.command.c_str());
            status_ = "Copied validation command.";
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        ImGui::BeginDisabled(validation_output.empty());
        if (ImGui::Button("Copy Output##validation")) {
            ImGui::SetClipboardText(validation_output.c_str());
            status_ = "Copied validation output.";
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Good Validation")) {
            RecordFeedback("liked", validation_payload, "validation_result; task_id=" + last_response_.task_id);
        }
        ImGui::SameLine();
        if (ImGui::Button("Bad Validation")) {
            RecordFeedback("disliked", validation_payload, "validation_result; task_id=" + last_response_.task_id);
        }
        ImGui::EndDisabled();
        if (!last_response_.validation.stdout_text.empty() || !last_response_.validation.stderr_text.empty()) {
            ImGui::BeginChild("validation_console", ImVec2(0, 190), true, ImGuiWindowFlags_HorizontalScrollbar);
            if (!last_response_.validation.stdout_text.empty()) {
                ImGui::TextUnformatted(last_response_.validation.stdout_text.c_str());
            }
            if (!last_response_.validation.stderr_text.empty()) {
                ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.94f, 0.36f, 0.36f, 1.0f));
                ImGui::TextUnformatted(last_response_.validation.stderr_text.c_str());
                ImGui::PopStyleColor();
            }
            ImGui::EndChild();
        }
    }

    if (!last_response_.repair_attempts.empty()) {
        ImGui::Separator();
        ImGui::TextUnformatted("Repair Attempts");
        if (ImGui::BeginTable("repair_attempt_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Attempt", ImGuiTableColumnFlags_WidthFixed, 70.0f);
            ImGui::TableSetupColumn("Outcome", ImGuiTableColumnFlags_WidthFixed, 116.0f);
            ImGui::TableSetupColumn("Category", ImGuiTableColumnFlags_WidthFixed, 100.0f);
            ImGui::TableSetupColumn("Summary");
            ImGui::TableSetupColumn("Checkpoint", ImGuiTableColumnFlags_WidthFixed, 118.0f);
            ImGui::TableHeadersRow();
            for (const RepairAttemptInfo& attempt : last_response_.repair_attempts) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextMuted(std::to_string(attempt.attempt));
                ImGui::TableSetColumnIndex(1);
                const bool good = attempt.outcome == "fixed" || attempt.outcome == "improved";
                const bool caution = attempt.outcome == "rolled_back" || attempt.outcome == "approval_blocked" || attempt.outcome == "no_patch";
                Pill(attempt.outcome.empty() ? "unknown" : attempt.outcome.c_str(),
                     good ? Rgba(38, 221, 123) : (caution ? Rgba(205, 154, 82) : Rgba(248, 113, 113)));
                ImGui::TableSetColumnIndex(2);
                TextMuted(attempt.category.empty() ? "unknown" : attempt.category);
                ImGui::TableSetColumnIndex(3);
                TextMuted(Shorten(attempt.summary.empty() ? attempt.before_signature : attempt.summary, 112));
                ImGui::TableSetColumnIndex(4);
                TextMuted(attempt.checkpoint.empty() ? "-" : Shorten(attempt.checkpoint, 18));
            }
            ImGui::EndTable();
        }
    }
}

void AegisChatApp::RenderChangesTab()
{
    if (!has_response_ || last_response_.changes.empty()) {
        TextMuted("Generated file changes will be previewed here.");
        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Open Checkpoint Browser", ImVec2(-1, 0))) {
            RefreshCheckpoints();
            pending_popup_ = "Aegis Checkpoints";
        }
        ImGui::EndDisabled();
        return;
    }

    const bool fully_applied = ResponseChangesFullyApplied(last_response_);
    const bool can_rollback = !last_response_.checkpoint.empty();
    const int applied_count = AppliedChangeCount(last_response_);
    selected_change_ = std::max(0, std::min(selected_change_, static_cast<int>(last_response_.changes.size()) - 1));
    const bool selected_applied = ChangeAlreadyApplied(last_response_, last_response_.changes[static_cast<size_t>(selected_change_)]);
    TextMuted(fully_applied
        ? "The generated changes are already written to the workspace."
        : (!last_response_.applied.empty()
            ? std::to_string(applied_count) + " change(s) applied; remaining items can still be applied."
            : std::to_string(last_response_.changes.size()) + " generated change(s) are waiting in preview."));
    ImGui::BeginDisabled(busy_ || fully_applied);
    if (ImGui::Button(fully_applied ? "Applied" : "Apply All Changes", ImVec2(-1, 0))) {
        ApplyPendingChanges();
    }
    ImGui::EndDisabled();
    ImGui::BeginDisabled(busy_ || selected_applied);
    if (ImGui::Button(selected_applied ? "Selected File Applied" : "Apply Selected File", ImVec2(-1, 0))) {
        ApplySelectedChange();
    }
    ImGui::EndDisabled();
    if (ImGui::Button("Copy Patch", ImVec2(-1, 0))) {
        CopyPatchToClipboard();
    }
    if (ImGui::Button("Export Patch", ImVec2(-1, 0))) {
        ExportPatchFile();
    }
    ImGui::BeginDisabled(busy_ || !can_rollback);
    if (ImGui::Button("Rollback Last Apply", ImVec2(-1, 0))) {
        RollbackLastApply();
    }
    ImGui::EndDisabled();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Open Checkpoint Browser", ImVec2(-1, 0))) {
        RefreshCheckpoints();
        pending_popup_ = "Aegis Checkpoints";
    }
    ImGui::EndDisabled();
    ImGui::Separator();

    ImGui::BeginChild("change_list", ImVec2(0, 170), true);
    for (int i = 0; i < static_cast<int>(last_response_.changes.size()); ++i) {
        const FileChange& change = last_response_.changes[i];
        const bool row_applied = ChangeAlreadyApplied(last_response_, change);
        std::string label = std::string(row_applied ? "[applied] " : "[preview] ") + change.action + " " + change.path + "##change" + std::to_string(i);
        if (ImGui::Selectable(label.c_str(), selected_change_ == i)) {
            selected_change_ = i;
            selected_hunk_ = 0;
        }
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("%s", change.summary.c_str());
        }
    }
    ImGui::EndChild();

    const FileChange& change = last_response_.changes[selected_change_];
    ImGui::TextWrapped("%s", change.path.c_str());
    TextMuted(change.summary);
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    const std::filesystem::path change_path = ResolveWorkspacePath(workspace, change.path);
    std::error_code change_ec;
    const bool change_file_exists = std::filesystem::exists(change_path, change_ec) && !std::filesystem::is_directory(change_path, change_ec);
    std::filesystem::path change_folder = change_file_exists ? change_path.parent_path() : ExistingParentOrSelf(change_path.parent_path());
    if (change_folder.empty()) {
        change_folder = ExistingParentOrSelf(ResolveWorkspacePath(workspace, ""));
    }
    const std::string change_payload =
        "Action: " + change.action +
        "\nPath: " + change.path +
        "\nSummary: " + change.summary +
        "\n\nContent:\n" + (change.has_content ? change.content : "[no file content included]");
    if (ImGui::Button("Copy Path##change")) {
        ImGui::SetClipboardText(change.path.c_str());
        status_ = "Copied change path.";
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(!change.has_content);
    if (ImGui::Button("Copy Content##change")) {
        ImGui::SetClipboardText(change.content.c_str());
        status_ = "Copied change content.";
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(!change_file_exists);
    if (ImGui::Button("Open File##change")) {
        OpenExternalPath(change_path);
        status_ = "Opened change file.";
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(change_folder.empty());
    if (ImGui::Button("Open Folder##change")) {
        OpenExternalPath(change_folder);
        status_ = "Opened change folder.";
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Like Change")) {
        RecordFeedback("liked", change_payload, "code_change; task_id=" + last_response_.task_id);
    }
    ImGui::SameLine();
    if (ImGui::Button("Reject Change")) {
        RecordFeedback("disliked", change_payload, "code_change; task_id=" + last_response_.task_id);
    }
    ImGui::EndDisabled();

    const std::vector<InlineDiffLine> diff_lines = BuildInlineDiffLines(change, workspace);
    const std::vector<SideBySideDiffRow> side_by_side_rows = BuildSideBySideDiffRows(diff_lines);
    const std::vector<DiffHunk> diff_hunks = BuildDiffHunks(diff_lines);
    const int added_lines = CountDiffMarker(diff_lines, '+');
    const int removed_lines = CountDiffMarker(diff_lines, '-');
    if (diff_hunks.empty()) {
        selected_hunk_ = 0;
    } else {
        selected_hunk_ = std::max(0, std::min(selected_hunk_, static_cast<int>(diff_hunks.size()) - 1));
    }
    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    if (diff_hunks.empty()) {
        TextMuted("No selectable hunks are available for this change.");
    } else {
        ImGui::PushItemWidth(std::min(360.0f, ImGui::GetContentRegionAvail().x));
        const std::string selected_label = HunkLabel(diff_hunks[static_cast<size_t>(selected_hunk_)]);
        if (ImGui::BeginCombo("Selected Hunk", selected_label.c_str())) {
            for (int i = 0; i < static_cast<int>(diff_hunks.size()); ++i) {
                const bool selected = selected_hunk_ == i;
                const std::string label = HunkLabel(diff_hunks[static_cast<size_t>(i)]);
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_hunk_ = i;
                }
                if (selected) {
                    ImGui::SetItemDefaultFocus();
                }
            }
            ImGui::EndCombo();
        }
        ImGui::PopItemWidth();
        ImGui::SameLine();
        ImGui::BeginDisabled(busy_ || selected_applied);
        if (ImGui::Button("Apply Selected Hunk")) {
            ApplySelectedHunk();
        }
        ImGui::EndDisabled();
        if (selected_applied) {
            ImGui::SameLine();
            TextMuted("File already fully applied.");
        }
    }
    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    if (ImGui::BeginTabBar("change_preview_tabs")) {
        if (ImGui::BeginTabItem("Inline Diff")) {
            TextMuted("+" + std::to_string(added_lines) + " additions, -" + std::to_string(removed_lines) + " removals.");
            ImGui::BeginChild("change_inline_diff", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
            if (diff_lines.empty()) {
                TextMuted("No line changes detected for this file.");
            } else if (ImGui::BeginTable(
                "change_inline_diff_table",
                4,
                ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingFixedFit | ImGuiTableFlags_NoSavedSettings)) {
                ImGui::TableSetupColumn("Old", ImGuiTableColumnFlags_WidthFixed, 48.0f);
                ImGui::TableSetupColumn("New", ImGuiTableColumnFlags_WidthFixed, 48.0f);
                ImGui::TableSetupColumn(" ", ImGuiTableColumnFlags_WidthFixed, 28.0f);
                ImGui::TableSetupColumn("Code", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                ImGuiListClipper clipper;
                clipper.Begin(static_cast<int>(diff_lines.size()));
                while (clipper.Step()) {
                    for (int row = clipper.DisplayStart; row < clipper.DisplayEnd; ++row) {
                        const InlineDiffLine& line = diff_lines[static_cast<size_t>(row)];
                        ImGui::TableNextRow();
                        if (line.marker == '+') {
                            ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, Color(18, 80, 47, 0.42f));
                        } else if (line.marker == '-') {
                            ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, Color(94, 37, 39, 0.44f));
                        }

                        ImGui::TableSetColumnIndex(0);
                        if (line.old_line > 0) {
                            TextMuted(std::to_string(line.old_line));
                        } else {
                            TextMuted("");
                        }
                        ImGui::TableSetColumnIndex(1);
                        if (line.new_line > 0) {
                            TextMuted(std::to_string(line.new_line));
                        } else {
                            TextMuted("");
                        }
                        ImGui::TableSetColumnIndex(2);
                        const ImVec4 marker_color = line.marker == '+'
                            ? Rgba(76, 236, 136)
                            : (line.marker == '-' ? Rgba(255, 126, 126) : Rgba(154, 164, 176));
                        ImGui::PushStyleColor(ImGuiCol_Text, marker_color);
                        const char marker_text[2] = {line.marker, '\0'};
                        ImGui::TextUnformatted(marker_text);
                        ImGui::PopStyleColor();
                        ImGui::TableSetColumnIndex(3);
                        ImGui::PushStyleColor(ImGuiCol_Text, marker_color);
                        ImGui::TextUnformatted(line.text.c_str());
                        ImGui::PopStyleColor();
                    }
                }
                ImGui::EndTable();
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Side By Side")) {
            TextMuted("Current file on the left, proposed result on the right.");
            ImGui::BeginChild("change_side_by_side_diff", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
            if (side_by_side_rows.empty()) {
                TextMuted("No line changes detected for this file.");
            } else if (ImGui::BeginTable(
                "change_side_by_side_diff_table",
                4,
                ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_BordersInnerV | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp | ImGuiTableFlags_NoSavedSettings)) {
                ImGui::TableSetupColumn("Old", ImGuiTableColumnFlags_WidthFixed, 48.0f);
                ImGui::TableSetupColumn("Current File", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                ImGui::TableSetupColumn("New", ImGuiTableColumnFlags_WidthFixed, 48.0f);
                ImGui::TableSetupColumn("Proposed File", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                ImGui::TableHeadersRow();

                ImGuiListClipper clipper;
                clipper.Begin(static_cast<int>(side_by_side_rows.size()));
                while (clipper.Step()) {
                    for (int row = clipper.DisplayStart; row < clipper.DisplayEnd; ++row) {
                        const SideBySideDiffRow& line = side_by_side_rows[static_cast<size_t>(row)];
                        ImGui::TableNextRow();
                        if (line.marker == '+') {
                            ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, Color(18, 80, 47, 0.38f));
                        } else if (line.marker == '-') {
                            ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, Color(94, 37, 39, 0.40f));
                        } else if (line.marker == '!') {
                            ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, Color(87, 63, 27, 0.34f));
                        }

                        ImGui::TableSetColumnIndex(0);
                        TextMuted(line.old_line > 0 ? std::to_string(line.old_line) : "");

                        ImGui::TableSetColumnIndex(1);
                        const ImVec4 old_color = line.marker == '-' || line.marker == '!'
                            ? Rgba(255, 126, 126)
                            : Rgba(207, 216, 226);
                        ImGui::PushStyleColor(ImGuiCol_Text, old_color);
                        ImGui::TextUnformatted(line.old_text.c_str());
                        ImGui::PopStyleColor();

                        ImGui::TableSetColumnIndex(2);
                        TextMuted(line.new_line > 0 ? std::to_string(line.new_line) : "");

                        ImGui::TableSetColumnIndex(3);
                        const ImVec4 new_color = line.marker == '+' || line.marker == '!'
                            ? Rgba(76, 236, 136)
                            : Rgba(207, 216, 226);
                        ImGui::PushStyleColor(ImGuiCol_Text, new_color);
                        ImGui::TextUnformatted(line.new_text.c_str());
                        ImGui::PopStyleColor();
                    }
                }
                ImGui::EndTable();
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }
        if (ImGui::BeginTabItem("Generated Content")) {
            ImGui::BeginChild("change_preview", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
            if (change.has_content) {
                ImGui::TextUnformatted(change.content.c_str());
            } else {
                TextMuted("This change does not include file content.");
            }
            ImGui::EndChild();
            ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
    }
}

void AegisChatApp::RenderWorkspaceTab()
{
    ImGui::TextWrapped("%s", workspace_root_.empty() ? "No workspace loaded." : workspace_root_.c_str());
    TextMuted(std::to_string(files_.size()) + " indexed file(s)");
    const std::string active_workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    const std::filesystem::path workspace_path = ResolveWorkspacePath(active_workspace, "");
    std::error_code workspace_ec;
    const bool workspace_exists = !active_workspace.empty() && std::filesystem::exists(workspace_path, workspace_ec);
    ImGui::BeginDisabled(!workspace_exists);
    if (ImGui::Button("Open Workspace Folder")) {
        OpenExternalPath(workspace_path);
        status_ = "Opened workspace folder.";
    }
    ImGui::EndDisabled();
    ImGui::Separator();

    if (!has_selected_file_) {
        TextMuted("Select a text file from the left panel to preview it.");
        return;
    }

    ImGui::TextWrapped("%s", selected_file_.path.c_str());
    const std::string selected_workspace = selected_file_.workspace_root.empty() ? active_workspace : selected_file_.workspace_root;
    const std::filesystem::path selected_path = ResolveWorkspacePath(selected_workspace, selected_file_.path);
    std::error_code selected_ec;
    const bool selected_file_exists = std::filesystem::exists(selected_path, selected_ec) && !std::filesystem::is_directory(selected_path, selected_ec);
    std::filesystem::path selected_folder = selected_file_exists ? selected_path.parent_path() : ExistingParentOrSelf(selected_path.parent_path());
    if (ImGui::Button("Copy File Path")) {
        ImGui::SetClipboardText(selected_file_.path.c_str());
        status_ = "Copied file path.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Copy File Content")) {
        ImGui::SetClipboardText(selected_file_.content.c_str());
        status_ = "Copied file content.";
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(!selected_file_exists);
    if (ImGui::Button("Open File")) {
        OpenExternalPath(selected_path);
        status_ = "Opened workspace file.";
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(selected_folder.empty());
    if (ImGui::Button("Open File Folder")) {
        OpenExternalPath(selected_folder);
        status_ = "Opened workspace file folder.";
    }
    ImGui::EndDisabled();
    ImGui::BeginChild("file_preview", ImVec2(0, 0), true, ImGuiWindowFlags_HorizontalScrollbar);
    ImGui::TextUnformatted(selected_file_.content.c_str());
    ImGui::EndChild();
}

void AegisChatApp::RenderEventsTab()
{
    const std::vector<ToolEvent>* events = has_response_ ? &last_response_.events : nullptr;
    if (events == nullptr || events->empty()) {
        TextMuted("Task events will appear after Aegis runs.");
    } else {
        for (const ToolEvent& event : *events) {
            ImGui::TextWrapped("%s", event.title.c_str());
            TextMuted(event.detail);
            ImGui::SameLine(ImGui::GetWindowWidth() - 72.0f);
            Pill(event.status.c_str(), event.status == "error" ? StatusColor(false) : StatusColor(true));
            ImGui::Separator();
        }
    }

    if (!recent_tasks_.empty()) {
        ImGui::TextUnformatted("History");
        for (const TaskSummary& task : recent_tasks_) {
            ImGui::BulletText("%s", Shorten(task.message, 92).c_str());
        }
    }
}

void AegisChatApp::RenderSettingsTab()
{
    ImGui::TextUnformatted("Desktop");
    ImGui::InputText("API base", api_base_buffer_.data(), api_base_buffer_.size());
    ImGui::InputText("Backend root", backend_root_buffer_.data(), backend_root_buffer_.size());
    ImGui::InputText("Start script", backend_script_buffer_.data(), backend_script_buffer_.size());
    ImGui::Checkbox("Auto start backend", &settings_.auto_start_backend);
    ImGui::SliderInt("Max files", &settings_.max_files, 20, 500);
    if (ImGui::Button("Save Desktop Settings")) {
        DesktopSettings next = BuildDesktopSettingsFromBuffers();
        next.auto_start_backend = settings_.auto_start_backend;
        next.max_files = settings_.max_files;
        SetBuffer(api_base_buffer_, next.api_base_url);
        SetBuffer(backend_root_buffer_, WideToUtf8(next.backend_root.wstring()));
        SetBuffer(backend_script_buffer_, next.backend_start_script);
        SaveDesktopSettingsFromUi();
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Backend Folder")) {
        OpenBackendFolder();
    }
    ImGui::SameLine();
    if (ImGui::Button("Start Backend")) {
        DesktopSettings next = BuildDesktopSettingsFromBuffers();
        next.auto_start_backend = true;
        client_.SetSettings(next);
        settings_ = next;
        RefreshRuntime(true);
    }
    ImGui::SameLine();
    if (ImGui::Button("Setup Check")) {
        pending_popup_ = "Aegis Setup Check";
        ImGui::CloseCurrentPopup();
        status_ = "Opened setup check.";
    }

    ImGui::Separator();
    ImGui::TextUnformatted("Aegis Core");
    ImGui::InputText("Assistant", assistant_name_buffer_.data(), assistant_name_buffer_.size());
    ImGui::InputTextMultiline("Mission", assistant_mission_buffer_.data(), assistant_mission_buffer_.size(), ImVec2(-1, 68));
    ImGui::InputText("Workspace", workspace_buffer_.data(), workspace_buffer_.size());
    ImGui::InputText("Model API", model_api_buffer_.data(), model_api_buffer_.size());
    ImGui::InputText("Model endpoint", model_endpoint_buffer_.data(), model_endpoint_buffer_.size());
    ImGui::InputText("Model name", model_name_buffer_.data(), model_name_buffer_.size());
    ImGui::InputTextMultiline("Allowlist", command_allowlist_buffer_.data(), command_allowlist_buffer_.size(), ImVec2(-1, 58));
    ImGui::SliderInt("Timeout", &config_.command_timeout_seconds, 5, 3600);
    ImGui::Checkbox("Auto validation", &run_validation_);
    RenderValidationProfilePanel();
    if (ImGui::Button("Save Aegis Settings", ImVec2(-1, 0))) {
        SaveRemoteConfigFromUi();
    }
}

void AegisChatApp::RenderValidationProfilePanel()
{
    ImGui::Separator();
    ImGui::TextUnformatted("Validation Profile");
    TextMuted("Choose the command Aegis should run for build, test, or type-check verification in the active workspace.");

    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    TextMuted("Workspace: " + Shorten(workspace.empty() ? "not selected" : workspace, 96));
    const std::vector<ValidationSuggestionInfo> local_suggestions = BuildProjectValidationSuggestions(files_);

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Load Profile")) {
        RefreshValidationProfile();
    }
    ImGui::SameLine();
    if (ImGui::Button("Run Validation")) {
        ValidateWorkspace();
    }
    ImGui::EndDisabled();

    ImGui::InputText("Validation command", validation_command_buffer_.data(), validation_command_buffer_.size());
    ImGui::InputText("Validation label", validation_label_buffer_.data(), validation_label_buffer_.size());
    ImGui::InputTextMultiline("Validation notes", validation_notes_buffer_.data(), validation_notes_buffer_.size(), ImVec2(-1, 52));

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Save Profile")) {
        SaveValidationProfile(false);
    }
    ImGui::SameLine();
    if (ImGui::Button("Clear Profile")) {
        SaveValidationProfile(true);
    }
    ImGui::EndDisabled();

    if (has_validation_profile_snapshot_) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        if (validation_profile_.has_profile) {
            TextColor("Active Recipe", Rgba(38, 221, 123));
            ImGui::BulletText("%s", validation_profile_.profile.command.c_str());
            if (!validation_profile_.profile.source.empty() || !validation_profile_.profile.notes.empty()) {
                TextMuted(
                    (validation_profile_.profile.source.empty() ? "manual" : validation_profile_.profile.source) +
                    (validation_profile_.profile.notes.empty() ? "" : " - " + validation_profile_.profile.notes));
            }
        } else {
            TextMuted("No saved validation profile yet. Pick a detected suggestion or enter a command manually.");
        }

        if (!local_suggestions.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Workspace Suggestions", Rgba(246, 248, 251));
            TextMuted("Aegis inferred these from visible workspace files before asking the backend.");
            RenderValidationSuggestionTable("local_validation_suggestions", local_suggestions, 8);
        }

        if (!validation_profile_.suggestions.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Detected Suggestions", Rgba(246, 248, 251));
            RenderValidationSuggestionTable("validation_suggestions", validation_profile_.suggestions, 5);
        }
    } else if (!local_suggestions.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Workspace Suggestions", Rgba(246, 248, 251));
        TextMuted("Aegis inferred these from visible workspace files.");
        RenderValidationSuggestionTable("local_validation_suggestions_no_profile", local_suggestions, 8);
    }
}

void AegisChatApp::RenderSetupCheckModal()
{
    TextColor("First-Run Setup Check", Rgba(246, 248, 251));
    TextMuted("Aegis checks the native desktop wiring before you start serious work: backend location, Python environment, launch script, API handshake, model readiness, workspace, and validation profile.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    DesktopSettings draft = BuildDesktopSettingsFromBuffers();
    draft.auto_start_backend = settings_.auto_start_backend;
    draft.max_files = settings_.max_files;

    std::error_code ec;
    const std::filesystem::path backend_root = draft.backend_root;
    const std::filesystem::path backend_main = backend_root / "backend" / "aegis_ai" / "main.py";
    const std::filesystem::path venv_python = backend_root / ".venv" / "Scripts" / "python.exe";
    const std::filesystem::path start_script = backend_root / Utf8ToWide(draft.backend_start_script);
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::filesystem::path workspace_path = workspace.empty() ? std::filesystem::path() : std::filesystem::path(Utf8ToWide(workspace));

    const bool backend_root_ok = !backend_root.empty() &&
        std::filesystem::exists(backend_root, ec) &&
        std::filesystem::is_directory(backend_root, ec);
    const bool backend_main_ok = std::filesystem::exists(backend_main, ec) && !std::filesystem::is_directory(backend_main, ec);
    const bool venv_ok = std::filesystem::exists(venv_python, ec) && !std::filesystem::is_directory(venv_python, ec);
    const bool start_script_ok = std::filesystem::exists(start_script, ec) && !std::filesystem::is_directory(start_script, ec);
    const bool launch_ok = venv_ok || start_script_ok;
    const std::string api_lower = Lower(draft.api_base_url);
    const bool api_configured = api_lower.rfind("http://", 0) == 0 || api_lower.rfind("https://", 0) == 0;
    const bool backend_online = health_.ok || health_.engine_ready;
    const bool model_configured = !Trim(models_.active_model).empty() || !Trim(BufferString(model_name_buffer_.data())).empty();
    const bool model_ready = health_.model_ready;
    const bool workspace_ok = !workspace.empty() &&
        std::filesystem::exists(workspace_path, ec) &&
        std::filesystem::is_directory(workspace_path, ec);
    const bool validation_ready = validation_profile_.has_profile || !Trim(BufferString(validation_command_buffer_.data())).empty();

    struct CheckRow {
        const char* name;
        bool ok;
        bool warning_only;
        std::string detail;
    };
    const CheckRow checks[] = {
        {"Backend root", backend_root_ok, false, backend_root_ok ? WideToUtf8(backend_root.wstring()) : "Set Backend root in Settings."},
        {"Backend app", backend_main_ok, false, backend_main_ok ? "backend/aegis_ai/main.py found." : "Missing backend/aegis_ai/main.py."},
        {"Python or start script", launch_ok, false, venv_ok ? "Using .venv/Scripts/python.exe." : (start_script_ok ? "Using configured PowerShell start script." : "Create the venv or fix the start script path.")},
        {"API base", api_configured, false, api_configured ? draft.api_base_url : "API base should start with http:// or https://."},
        {"Backend handshake", backend_online, false, backend_online ? "FastAPI runtime is responding." : "Click Start Backend or Refresh Runtime."},
        {"Model server", model_ready, false, model_ready ? (health_.model_message.empty() ? "Active model is ready." : health_.model_message) : (model_configured ? "Model configured but not ready." : "Configure an active model.")},
        {"Workspace", workspace_ok, false, workspace_ok ? workspace : "Pick an existing workspace folder."},
        {"Validation profile", validation_ready, true, validation_ready ? "A build/test command is saved or staged." : "Optional but recommended before auto-apply work."},
    };

    int ready_count = 0;
    int required_count = 0;
    int required_ready = 0;
    for (const CheckRow& check : checks) {
        if (check.ok) {
            ++ready_count;
        }
        if (!check.warning_only) {
            ++required_count;
            if (check.ok) {
                ++required_ready;
            }
        }
    }

    const bool required_ok = required_ready == required_count;
    TextMuted("Required checks: " + std::to_string(required_ready) + " / " + std::to_string(required_count));
    constexpr int check_count = static_cast<int>(sizeof(checks) / sizeof(checks[0]));
    DrawProgress(static_cast<float>(ready_count) / static_cast<float>(check_count), ImVec2(ImGui::GetContentRegionAvail().x, 8.0f), !required_ok);
    ImGui::Dummy(ImVec2(0.0f, 10.0f));

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Runtime")) {
        RefreshRuntime(false);
    }
    ImGui::SameLine();
    if (ImGui::Button("Start Backend")) {
        settings_ = draft;
        settings_.auto_start_backend = true;
        client_.SetSettings(settings_);
        RefreshRuntime(true);
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Open Settings")) {
        pending_popup_ = "Aegis Settings";
        ImGui::CloseCurrentPopup();
        status_ = "Opened settings.";
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(!backend_root_ok);
    if (ImGui::Button("Backend Folder")) {
        OpenExternalPath(backend_root);
        status_ = "Opened backend folder.";
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(!workspace_ok);
    if (ImGui::Button("Workspace Folder")) {
        OpenExternalPath(workspace_path);
        status_ = "Opened workspace folder.";
    }
    ImGui::EndDisabled();
    ImGui::Separator();

    if (ImGui::BeginTable("setup_check_table", 3, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 92.0f);
        ImGui::TableSetupColumn("Check", ImGuiTableColumnFlags_WidthFixed, 170.0f);
        ImGui::TableSetupColumn("Detail", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableHeadersRow();

        for (const CheckRow& check : checks) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const bool warning = check.warning_only && !check.ok;
            Pill(check.ok ? "Ready" : (warning ? "Advised" : "Fix"), check.ok ? StatusColor(true) : (warning ? Rgba(205, 154, 82) : StatusColor(false)));
            ImGui::TableSetColumnIndex(1);
            TextColor(check.name, check.ok ? Rgba(246, 248, 251) : (warning ? Rgba(205, 154, 82) : Rgba(248, 113, 113)));
            ImGui::TableSetColumnIndex(2);
            TextMuted(check.detail);
        }

        ImGui::EndTable();
    }

    ImGui::Separator();
    if (required_ok) {
        TextColor("Core desktop setup is ready.", Rgba(38, 221, 123));
        TextMuted("The next high-value work is model registry/routing, streaming responses, and richer Creative Studio previews.");
    } else {
        TextColor("Finish the red checks before relying on chat, coding tools, or media jobs.", Rgba(248, 113, 113));
        TextMuted("The dashboard can still render while Aegis is offline, but generation, workspace context, and model inventory depend on these runtime checks.");
    }
}

void AegisChatApp::RenderContextPreviewModal()
{
    TextColor("Context Preview", Rgba(246, 248, 251));
    TextMuted("Review what the desktop is about to send directly, what the backend can inspect from the active workspace, and whether the selected model target appears local or cloud-hosted.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    const std::string active_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string active_model = models_.active_model.empty() ? config_.model_name : models_.active_model;
    const std::string active_api = models_.active_api.empty() ? BufferString(model_api_buffer_.data()) : models_.active_api;
    const std::string active_endpoint = models_.active_endpoint.empty() ? BufferString(model_endpoint_buffer_.data()) : models_.active_endpoint;
    const bool cloud_target = IsCloudModelTarget(active_api, active_endpoint);
    const std::string composer_text = Trim(std::string(message_buffer_.data()));

    if (ImGui::BeginTable("context_summary", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Model", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 120.0f);
        ImGui::TableSetupColumn("Target", ImGuiTableColumnFlags_WidthFixed, 96.0f);
        ImGui::TableSetupColumn("Composer", ImGuiTableColumnFlags_WidthFixed, 94.0f);
        ImGui::TableHeadersRow();
        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        TextColor(active_model.empty() ? "Not configured" : Shorten(active_model, 54), Rgba(246, 248, 251));
        ImGui::TableSetColumnIndex(1);
        TextMuted(active_api.empty() ? "unknown" : active_api);
        ImGui::TableSetColumnIndex(2);
        Pill(cloud_target ? "Cloud" : "Local", cloud_target ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
        ImGui::TableSetColumnIndex(3);
        TextMuted(std::to_string(composer_text.size()) + " chars");
        ImGui::EndTable();
    }

    if (cloud_target && (!active_workspace.empty() || !attachments_.empty())) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Cloud-context warning", Rgba(205, 154, 82));
        TextMuted("This model target is not loopback/local. Attached text and any backend-selected workspace context may be sent to the provider configured in Settings.");
    }

    std::vector<ContextRisk> context_risks = ScanTextForContextRisks("Composer", composer_text);
    for (const FileContent& attachment : attachments_) {
        std::vector<ContextRisk> path_risks = ScanPathForContextRisks("Attachment path", attachment.path);
        context_risks.insert(context_risks.end(), path_risks.begin(), path_risks.end());
        std::vector<ContextRisk> text_risks = ScanTextForContextRisks("Attachment: " + Shorten(attachment.path, 48), attachment.content);
        context_risks.insert(context_risks.end(), text_risks.begin(), text_risks.end());
    }
    const int workspace_scan_count = std::min(24, static_cast<int>(files_.size()));
    for (int i = 0; i < workspace_scan_count; ++i) {
        std::vector<ContextRisk> path_risks = ScanPathForContextRisks("Workspace: " + Shorten(files_[i].path, 52), files_[i].path);
        context_risks.insert(context_risks.end(), path_risks.begin(), path_risks.end());
    }
    if (has_response_) {
        for (const WorkspaceFile& file : last_response_.context_files) {
            std::vector<ContextRisk> path_risks = ScanPathForContextRisks("Last context: " + Shorten(file.path, 48), file.path);
            context_risks.insert(context_risks.end(), path_risks.begin(), path_risks.end());
        }
    }

    size_t history_chars = 0;
    for (const ChatMessage& message : history_) {
        history_chars += message.content.size();
    }

    size_t attachment_chars = 0;
    for (const FileContent& attachment : attachments_) {
        attachment_chars += attachment.content.size();
    }

    size_t workspace_index_chars = 0;
    for (const WorkspaceFile& file : files_) {
        workspace_index_chars += file.path.size() + file.kind.size() + 32;
    }

    size_t last_context_chars = 0;
    if (has_response_) {
        for (const WorkspaceFile& file : last_response_.context_files) {
            last_context_chars += file.path.size() + file.kind.size() + 32;
        }
    }

    const size_t memory_signal_chars = recent_tasks_.size() * 180;
    const size_t direct_chars = composer_text.size() + attachment_chars + history_chars;
    const size_t total_context_chars = direct_chars + workspace_index_chars + last_context_chars + memory_signal_chars;
    const int composer_tokens = ApproxTokensFromChars(composer_text.size());
    const int attachment_tokens = ApproxTokensFromChars(attachment_chars);
    const int history_tokens = ApproxTokensFromChars(history_chars);
    const int workspace_tokens = ApproxTokensFromChars(workspace_index_chars);
    const int last_context_tokens = ApproxTokensFromChars(last_context_chars);
    const int memory_tokens = ApproxTokensFromChars(memory_signal_chars);
    const int total_tokens = ApproxTokensFromChars(total_context_chars);
    const int soft_budget = cloud_target ? 128000 : 32000;
    const float budget_fraction = Clamp01(static_cast<float>(total_tokens) / static_cast<float>(soft_budget));

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Token Budget Planner", Rgba(246, 248, 251));
    TextMuted("Estimates are approximate. The backend may send only a relevant subset of workspace context, but this gives you a safety read before the request leaves the desktop.");
    DrawProgress(budget_fraction, ImVec2(ImGui::GetContentRegionAvail().x, 8.0f), budget_fraction > 0.62f);
    TextMuted("Estimated total: " + std::to_string(total_tokens) + " / " + std::to_string(soft_budget) + " soft-budget tokens");

    if (budget_fraction >= 0.85f) {
        TextColor("High context load: remove large attachments or narrow the workspace before sending.", Rgba(248, 113, 113));
    } else if (budget_fraction >= 0.62f) {
        TextColor("Moderate context load: this should work, but focused attachments will improve speed and answer quality.", Rgba(205, 154, 82));
    } else {
        TextColor("Context load looks healthy for the selected target.", Rgba(38, 221, 123));
    }

    if (ImGui::BeginTable("context_token_budget_table", 3, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Source");
        ImGui::TableSetupColumn("Chars", ImGuiTableColumnFlags_WidthFixed, 88.0f);
        ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 88.0f);
        ImGui::TableHeadersRow();
        const auto budget_row = [](const char* label, size_t chars, int tokens) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(label);
            ImGui::TableSetColumnIndex(1);
            TextMuted(std::to_string(chars));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(tokens));
        };
        budget_row("Composer text", composer_text.size(), composer_tokens);
        budget_row("Explicit attachments", attachment_chars, attachment_tokens);
        budget_row("Conversation history", history_chars, history_tokens);
        budget_row("Workspace index snapshot", workspace_index_chars, workspace_tokens);
        budget_row("Last response context", last_context_chars, last_context_tokens);
        budget_row("Memory/task signals", memory_signal_chars, memory_tokens);
        ImGui::EndTable();
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Pre-Send Safety Scan", Rgba(246, 248, 251));
    if (context_risks.empty()) {
        TextColor("No obvious secrets or prompt-injection markers found in the visible send context.", Rgba(38, 221, 123));
        TextMuted("This is a local heuristic scan, not a substitute for careful review before sending private project content to a cloud model.");
    } else {
        int high_count = 0;
        int medium_count = 0;
        for (const ContextRisk& risk : context_risks) {
            const std::string severity = Lower(risk.severity);
            if (severity == "high") {
                ++high_count;
            } else if (severity == "medium") {
                ++medium_count;
            }
        }
        const std::string summary = std::to_string(context_risks.size()) + " issue(s) found: " +
            std::to_string(high_count) + " high, " + std::to_string(medium_count) + " medium.";
        TextColor(summary, high_count > 0 ? Rgba(248, 113, 113) : Rgba(205, 154, 82));
        TextMuted("Review or remove risky attachments before sending. Secret-looking content should not be sent to cloud providers.");

        if (ImGui::Button("Copy Safety Summary")) {
            std::ostringstream summary_text;
            summary_text << "Aegis Context Preview safety scan\n";
            for (const ContextRisk& risk : context_risks) {
                summary_text << "- [" << risk.severity << "] " << risk.finding << " / " << risk.source << ": " << risk.detail << "\n";
            }
            ImGui::SetClipboardText(summary_text.str().c_str());
            status_ = "Copied context safety summary.";
        }

        if (ImGui::BeginTable("context_safety_scan_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Severity", ImGuiTableColumnFlags_WidthFixed, 78.0f);
            ImGui::TableSetupColumn("Source", ImGuiTableColumnFlags_WidthFixed, 190.0f);
            ImGui::TableSetupColumn("Finding", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableSetupColumn("Detail");
            ImGui::TableHeadersRow();
            const int count = std::min(12, static_cast<int>(context_risks.size()));
            for (int i = 0; i < count; ++i) {
                const ContextRisk& risk = context_risks[i];
                const std::string severity = Lower(risk.severity);
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                Pill(risk.severity.c_str(), severity == "high" ? Rgba(248, 113, 113) : (severity == "medium" ? Rgba(205, 154, 82) : Rgba(133, 146, 161)));
                ImGui::TableSetColumnIndex(1);
                TextMuted(Shorten(risk.source, 42));
                ImGui::TableSetColumnIndex(2);
                TextColor(risk.finding, severity == "high" ? Rgba(248, 180, 180) : Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(3);
                TextMuted(risk.detail);
            }
            ImGui::EndTable();
            if (context_risks.size() > 12) {
                TextMuted("Showing 12 of " + std::to_string(context_risks.size()) + " safety finding(s).");
            }
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Attach Selected File")) {
        AttachSelectedFile();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Open Model Stack")) {
        pending_popup_ = "Aegis Model Stack";
        ImGui::CloseCurrentPopup();
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Settings")) {
        pending_popup_ = "Aegis Settings";
        ImGui::CloseCurrentPopup();
    }
    ImGui::Separator();

    TextColor("Explicit Next Message Context", Rgba(246, 248, 251));
    if (attachments_.empty()) {
        TextMuted("No files are attached. The next message will send only the composer text plus normal conversation history.");
    } else if (ImGui::BeginTable("attached_context_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("File");
        ImGui::TableSetupColumn("Chars", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Workspace", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Remove", ImGuiTableColumnFlags_WidthFixed, 76.0f);
        ImGui::TableHeadersRow();
        for (size_t i = 0; i < attachments_.size(); ++i) {
            ImGui::PushID(static_cast<int>(i));
            const FileContent& attachment = attachments_[i];
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextColor(Shorten(attachment.path, 44), Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(1);
            TextMuted(std::to_string(attachment.content.size()));
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(attachment.workspace_root.empty() ? active_workspace : attachment.workspace_root, 62));
            ImGui::TableSetColumnIndex(3);
            if (ImGui::Button("Remove")) {
                RemoveAttachment(i);
                ImGui::PopID();
                break;
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Workspace Available To Backend", Rgba(246, 248, 251));
    TextMuted(active_workspace.empty() ? "No workspace is selected." : active_workspace);
    if (files_.empty()) {
        TextMuted("No workspace files are loaded in the desktop snapshot yet.");
    } else if (ImGui::BeginTable("workspace_context_table", 3, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("File");
        ImGui::TableSetupColumn("Kind", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Size", ImGuiTableColumnFlags_WidthFixed, 88.0f);
        ImGui::TableHeadersRow();
        const int count = std::min(12, static_cast<int>(files_.size()));
        for (int i = 0; i < count; ++i) {
            const WorkspaceFile& file = files_[i];
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(file.path, 70));
            ImGui::TableSetColumnIndex(1);
            TextMuted(file.kind.empty() ? "file" : file.kind);
            ImGui::TableSetColumnIndex(2);
            TextMuted(FormatBytes(file.size));
        }
        ImGui::EndTable();
        if (files_.size() > 12) {
            TextMuted("Showing 12 of " + std::to_string(files_.size()) + " loaded workspace file(s). Backend retrieval may select a smaller relevant subset per request.");
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Last Response Context", Rgba(246, 248, 251));
    if (!has_response_ || last_response_.context_files.empty()) {
        TextMuted("No previous response context files are available yet.");
    } else {
        for (const WorkspaceFile& file : last_response_.context_files) {
            ImGui::BulletText("%s", file.path.c_str());
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Memory Signals", Rgba(246, 248, 251));
    TextMuted("Feedback, recent tasks, and user-created notes are saved through the backend memory/history system.");
    TextMuted("Recent backend task summaries loaded: " + std::to_string(recent_tasks_.size()));
    TextMuted("Memory Center notes loaded: " + std::to_string(memory_notes_.size()));
    if (ImGui::Button("Open Memory Center")) {
        RefreshMemoryNotes();
        pending_popup_ = "Aegis Memory Center";
        status_ = "Opened memory center.";
    }
}

void AegisChatApp::RenderConversationBrowserModal()
{
    TextColor("Conversations", Rgba(246, 248, 251));
    TextMuted("Local conversation library for the native desktop app. Saved chats stay under Aegis app data and can be loaded, pinned, archived, searched, or deleted.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (ImGui::Button("Refresh")) {
        RefreshConversationLibrary();
        status_ = "Refreshed conversations.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Save Current")) {
        SaveConversationSnapshot();
        RefreshConversationLibrary();
        status_ = "Saved current conversation.";
    }
    ImGui::SameLine();
    if (ImGui::Button(current_conversation_pinned_ ? "Unpin Current" : "Pin Current")) {
        current_conversation_pinned_ = !current_conversation_pinned_;
        SaveConversationSnapshot();
        RefreshConversationLibrary();
        status_ = current_conversation_pinned_ ? "Pinned current conversation." : "Unpinned current conversation.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Folder")) {
        OpenExternalPath(ConversationLibraryDirectory());
    }

    ImGui::Separator();
    ImGui::Columns(4, "conversation_browser_summary", false);
    TextMuted("Current");
    TextColor(current_conversation_title_.empty() ? ConversationTitleFromHistory(history_) : Shorten(current_conversation_title_, 34), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Messages");
    TextColor(std::to_string(history_.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Saved Chats");
    TextColor(std::to_string(conversations_.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("State");
    TextColor(current_conversation_archived_ ? "Archived" : (current_conversation_pinned_ ? "Pinned" : "Active"),
              current_conversation_archived_ ? Rgba(205, 154, 82) : (current_conversation_pinned_ ? Rgba(38, 221, 123) : Rgba(246, 248, 251)));
    ImGui::Columns(1);

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(10, 17, 25));
    ImGui::PushStyleColor(ImGuiCol_FrameBgHovered, Rgba(16, 25, 36));
    ImGui::PushStyleColor(ImGuiCol_FrameBgActive, Rgba(16, 30, 39));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(46, 59, 72));
    ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 8.0f);
    ImGui::PushItemWidth(520.0f);
    ImGui::InputTextWithHint("##conversation_search", "Search title, preview, or saved time", conversation_search_buffer_.data(), conversation_search_buffer_.size());
    ImGui::PopItemWidth();
    ImGui::PopStyleVar(2);
    ImGui::PopStyleColor(4);
    ImGui::SameLine();
    ImGui::Checkbox("Show archived", &show_archived_conversations_);

    const std::string filter = BufferString(conversation_search_buffer_.data());
    int visible = 0;
    for (const LocalConversationSummary& summary : conversations_) {
        if (!show_archived_conversations_ && summary.archived) {
            continue;
        }
        if (!filter.empty() &&
            !ContainsCaseInsensitive(summary.title, filter) &&
            !ContainsCaseInsensitive(summary.preview, filter) &&
            !ContainsCaseInsensitive(summary.saved_at, filter)) {
            continue;
        }
        ++visible;
    }

    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    TextMuted(std::to_string(visible) + " visible conversation(s)");
    if (visible == 0) {
        TextMuted("No conversations match this view. Save the current chat or clear the search filter.");
        return;
    }

    if (ImGui::BeginTable("conversation_browser_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("State", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableSetupColumn("Title");
        ImGui::TableSetupColumn("Preview");
        ImGui::TableSetupColumn("Saved", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Load", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableSetupColumn("Pin", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableSetupColumn("Archive/Delete", ImGuiTableColumnFlags_WidthFixed, 142.0f);
        ImGui::TableHeadersRow();

        for (int i = 0; i < static_cast<int>(conversations_.size()); ++i) {
            const LocalConversationSummary& summary = conversations_[i];
            if (!show_archived_conversations_ && summary.archived) {
                continue;
            }
            if (!filter.empty() &&
                !ContainsCaseInsensitive(summary.title, filter) &&
                !ContainsCaseInsensitive(summary.preview, filter) &&
                !ContainsCaseInsensitive(summary.saved_at, filter)) {
                continue;
            }

            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            Pill(summary.archived ? "Archive" : (summary.pinned ? "Pinned" : (summary.id == current_conversation_id_ ? "Open" : "Saved")),
                 summary.archived ? Rgba(205, 154, 82) : (summary.pinned ? Rgba(38, 221, 123) : Rgba(133, 146, 161)));
            ImGui::TableSetColumnIndex(1);
            TextColor(Shorten(summary.title, 44), summary.id == current_conversation_id_ ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(summary.preview, 64));
            ImGui::TableSetColumnIndex(3);
            TextMuted(summary.saved_at.empty() ? "-" : Shorten(summary.saved_at, 12));
            ImGui::TableSetColumnIndex(4);
            if (ImGui::Button("Load", ImVec2(-1.0f, 0.0f))) {
                LoadConversationFromLibrary(i);
                ImGui::PopID();
                break;
            }
            ImGui::TableSetColumnIndex(5);
            if (ImGui::Button(summary.pinned ? "Unpin" : "Pin", ImVec2(-1.0f, 0.0f))) {
                ToggleConversationPinned(i);
                ImGui::PopID();
                break;
            }
            ImGui::TableSetColumnIndex(6);
            if (ImGui::Button(summary.archived ? "Restore" : "Archive")) {
                ToggleConversationArchived(i);
                ImGui::PopID();
                break;
            }
            ImGui::SameLine();
            if (ImGui::Button("Delete")) {
                DeleteConversationFromLibrary(i);
                ImGui::PopID();
                break;
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
}

void AegisChatApp::RenderMemoryCenterModal()
{
    TextColor("Memory Center", Rgba(246, 248, 251));
    TextMuted("Inspect and edit the project/user facts Aegis can use as memory. Keep only things you want future tasks to remember.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (!memory_notes_loaded_ && !busy_) {
        RefreshMemoryNotes();
    }

    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    TextMuted("Workspace: " + Shorten(workspace.empty() ? "not selected" : workspace, 112));

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Memory")) {
        RefreshMemoryNotes();
    }
    ImGui::SameLine();
    if (ImGui::Button("New Memory")) {
        HydrateMemoryEditor(nullptr, -1);
    }
    ImGui::SameLine();
    if (ImGui::Button("Remember Current Goal")) {
        const std::string goal = Trim(std::string(message_buffer_.data()));
        HydrateMemoryEditor(nullptr, -1);
        SetBuffer(memory_title_buffer_, goal.empty() ? "Current project preference" : Shorten(goal, 120));
        SetBuffer(memory_content_buffer_, goal.empty() ? "Describe the fact, preference, constraint, or decision Aegis should remember." : goal);
        SetBuffer(memory_category_buffer_, "preference");
        SetBuffer(memory_tags_buffer_, "desktop, project");
        memory_note_pinned_ = true;
    }
    ImGui::EndDisabled();

    ImGui::SameLine();
    if (ImGui::Button("Open Memory Folder")) {
        if (!workspace.empty()) {
            OpenExternalPath(std::filesystem::path(Utf8ToWide(workspace)) / "memory");
        }
    }

    ImGui::Separator();
    ImGui::Columns(4, "memory_summary_columns", false);
    TextMuted("Notes");
    TextColor(std::to_string(memory_notes_.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Pinned");
    const int pinned_count = static_cast<int>(std::count_if(memory_notes_.begin(), memory_notes_.end(), [](const MemoryNoteInfo& note) {
        return note.pinned;
    }));
    TextColor(std::to_string(pinned_count), Rgba(38, 221, 123));
    ImGui::NextColumn();
    TextMuted("Selected");
    TextColor(selected_memory_note_index_ >= 0 && selected_memory_note_index_ < static_cast<int>(memory_notes_.size())
        ? Shorten(memory_notes_[selected_memory_note_index_].title, 28)
        : "new note", Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Privacy");
    TextColor("workspace-local", Rgba(205, 154, 82));
    ImGui::Columns(1);

    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    ImGui::InputTextWithHint("##memory_search", "Search memory title, category, content, or tags", memory_search_buffer_.data(), memory_search_buffer_.size());

    ImGui::BeginChild("memory_note_list", ImVec2(310.0f, 420.0f), true);
    TextColor("Saved Notes", Rgba(246, 248, 251));
    const std::string query = Lower(BufferString(memory_search_buffer_.data()));
    if (memory_notes_.empty()) {
        TextMuted("No memory notes loaded yet. Add a preference, project decision, reusable fix, or learning goal.");
    } else {
        for (int i = 0; i < static_cast<int>(memory_notes_.size()); ++i) {
            const MemoryNoteInfo& note = memory_notes_[i];
            const std::string haystack = Lower(note.title + "\n" + note.category + "\n" + note.content + "\n" + JoinPalette(note.tags));
            if (!query.empty() && haystack.find(query) == std::string::npos) {
                continue;
            }
            const std::string title = (note.pinned ? "[pinned] " : "") + Shorten(note.title.empty() ? note.id : note.title, 34);
            const std::string subtitle = Shorten((note.category.empty() ? "insight" : note.category) + " / " + (note.updated_at.empty() ? note.created_at : note.updated_at), 44);
            if (RowButton(("memory_note_" + std::to_string(i)).c_str(), IconGlyph::History, title.c_str(), subtitle.c_str(), i == selected_memory_note_index_)) {
                HydrateMemoryEditor(&note, i);
            }
        }
    }
    ImGui::EndChild();

    ImGui::SameLine();
    ImGui::BeginChild("memory_note_editor", ImVec2(0.0f, 420.0f), true);
    TextColor(selected_memory_note_index_ >= 0 ? "Edit Memory" : "New Memory", Rgba(246, 248, 251));
    TextMuted("Use memory for durable preferences, constraints, project decisions, recurring fixes, and learning goals.");
    ImGui::InputText("Title", memory_title_buffer_.data(), memory_title_buffer_.size());
    ImGui::InputText("Category", memory_category_buffer_.data(), memory_category_buffer_.size());
    ImGui::InputText("Tags", memory_tags_buffer_.data(), memory_tags_buffer_.size());
    ImGui::InputText("Related files", memory_related_files_buffer_.data(), memory_related_files_buffer_.size());
    ImGui::Checkbox("Pinned", &memory_note_pinned_);
    ImGui::SameLine();
    float confidence = static_cast<float>(memory_note_confidence_);
    ImGui::SetNextItemWidth(220.0f);
    if (ImGui::SliderFloat("Confidence", &confidence, 0.0f, 1.0f, "%.2f")) {
        memory_note_confidence_ = confidence;
    }
    ImGui::InputTextMultiline("Content", memory_content_buffer_.data(), memory_content_buffer_.size(), ImVec2(-1.0f, 150.0f));

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Save Memory")) {
        SaveMemoryNoteFromEditor();
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(selected_memory_note_index_ < 0);
    if (ImGui::Button("Delete Memory")) {
        DeleteSelectedMemoryNote();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Copy Content")) {
        ImGui::SetClipboardText(BufferString(memory_content_buffer_.data()).c_str());
        status_ = "Copied memory content.";
    }
    ImGui::EndDisabled();

    if (selected_memory_note_index_ >= 0 && selected_memory_note_index_ < static_cast<int>(memory_notes_.size())) {
        const MemoryNoteInfo& note = memory_notes_[selected_memory_note_index_];
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextMuted("Id: " + note.id);
        TextMuted("Created: " + (note.created_at.empty() ? "unknown" : note.created_at));
        TextMuted("Updated: " + (note.updated_at.empty() ? "unknown" : note.updated_at));
    }
    ImGui::EndChild();

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Memory Guidance", Rgba(246, 248, 251));
    ImGui::BulletText("Preference: UI, tone, workflow, model, privacy, or creative taste the user wants remembered.");
    ImGui::BulletText("Constraint: project rules, safety boundaries, deployment requirements, or technology choices.");
    ImGui::BulletText("Fix: reusable error/fix knowledge that should help future validation repairs.");
}

void AegisChatApp::RenderCheckpointBrowserModal()
{
    TextColor("Checkpoint Browser", Rgba(246, 248, 251));
    TextMuted("Restore points created before Aegis writes files. Pick one to inspect the affected files, then restore only when the selected workspace is the one you want.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    const std::string active_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    if (ImGui::Button("Refresh")) {
        RefreshCheckpoints();
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(active_workspace.empty());
    if (ImGui::Button("Open Checkpoint Folder")) {
        OpenExternalPath(std::filesystem::path(Utf8ToWide(active_workspace)) / ".aegis" / "checkpoints");
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_ || checkpoints_.checkpoints.empty() || selected_checkpoint_index_ < 0);
    if (ImGui::Button("Restore Selected")) {
        RestoreCheckpointFromBrowser();
    }
    ImGui::EndDisabled();

    ImGui::Separator();
    ImGui::Columns(3, "checkpoint_summary", false);
    TextMuted("Workspace");
    TextColor(active_workspace.empty() ? "No workspace selected" : Shorten(active_workspace, 72), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Restore points");
    TextColor(std::to_string(checkpoints_.checkpoints.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Selected");
    if (selected_checkpoint_index_ >= 0 && selected_checkpoint_index_ < static_cast<int>(checkpoints_.checkpoints.size())) {
        TextColor(Shorten(checkpoints_.checkpoints[static_cast<size_t>(selected_checkpoint_index_)].id, 24), Rgba(246, 248, 251));
    } else {
        TextMuted("None");
    }
    ImGui::Columns(1);

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    if (checkpoints_.checkpoints.empty()) {
        TextMuted(busy_ ? "Loading checkpoint history..." : "No checkpoints are loaded yet. Apply a change or refresh this browser after file writes.");
        return;
    }

    selected_checkpoint_index_ = std::max(
        0,
        std::min(selected_checkpoint_index_, static_cast<int>(checkpoints_.checkpoints.size()) - 1));

    ImGui::BeginChild("checkpoint_browser_list", ImVec2(0.0f, 214.0f), true);
    if (ImGui::BeginTable("checkpoint_browser_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Checkpoint");
        ImGui::TableSetupColumn("Created", ImGuiTableColumnFlags_WidthFixed, 164.0f);
        ImGui::TableSetupColumn("Files", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableSetupColumn("Restore", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Remove", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableHeadersRow();

        for (int i = 0; i < static_cast<int>(checkpoints_.checkpoints.size()); ++i) {
            const CheckpointSummaryInfo& checkpoint = checkpoints_.checkpoints[static_cast<size_t>(i)];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const std::string row_label = Shorten(checkpoint.id, 44) + "##checkpoint";
            if (ImGui::Selectable(row_label.c_str(), selected_checkpoint_index_ == i, ImGuiSelectableFlags_SpanAllColumns)) {
                selected_checkpoint_index_ = i;
            }
            ImGui::TableSetColumnIndex(1);
            TextMuted(CheckpointDisplayTime(checkpoint));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(checkpoint.file_count));
            ImGui::TableSetColumnIndex(3);
            TextMuted(std::to_string(checkpoint.present_count));
            ImGui::TableSetColumnIndex(4);
            TextMuted(std::to_string(checkpoint.missing_count));
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
    ImGui::EndChild();

    const CheckpointSummaryInfo& selected = checkpoints_.checkpoints[static_cast<size_t>(selected_checkpoint_index_)];
    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Selected Restore Point", Rgba(246, 248, 251));
    TextMuted(selected.id);
    TextMuted("Created: " + CheckpointDisplayTime(selected));
    TextMuted(
        std::to_string(selected.file_count) + " file(s), " +
        std::to_string(selected.present_count) + " existing file restore(s), " +
        std::to_string(selected.missing_count) + " created file removal(s).");

    if (ImGui::Button("Copy Checkpoint ID")) {
        ImGui::SetClipboardText(selected.id.c_str());
        status_ = "Copied checkpoint id.";
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Restore This Checkpoint")) {
        RestoreCheckpointFromBrowser();
    }
    ImGui::EndDisabled();

    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    ImGui::BeginChild("checkpoint_file_list", ImVec2(0.0f, 174.0f), true);
    if (selected.files.empty()) {
        TextMuted("This checkpoint manifest does not list any files.");
    } else if (ImGui::BeginTable("checkpoint_file_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("State", ImGuiTableColumnFlags_WidthFixed, 86.0f);
        ImGui::TableSetupColumn("Path");
        ImGui::TableHeadersRow();
        for (const CheckpointFileInfo& file : selected.files) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const bool restores_file = file.state == "present";
            Pill(restores_file ? "Restore" : "Remove", restores_file ? Rgba(111, 180, 255) : Rgba(205, 154, 82));
            ImGui::TableSetColumnIndex(1);
            TextMuted(Shorten(file.path, 104));
        }
        ImGui::EndTable();
    }
    ImGui::EndChild();
}

void AegisChatApp::RenderModelStackModal()
{
    TextColor("Model Stack", Rgba(246, 248, 251));
    TextMuted("This is the first desktop slice of the multi-model roadmap: live inventory, active model state, capability visibility, and the next router targets.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (ImGui::Button("Refresh Inventory")) {
        RefreshRuntime(false);
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Model Settings")) {
        status_ = "Model API, endpoint, and name are editable in Aegis Settings.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Master TODO")) {
        OpenExternalPath(ProjectDirectoryFromExecutable() / "PROJECT_TODO.md");
    }
    ImGui::Separator();

    const std::string active_model = models_.active_model.empty() ? config_.model_name : models_.active_model;
    const std::string active_api = models_.active_api.empty() ? config_.model_api : models_.active_api;
    const std::string active_endpoint = models_.active_endpoint.empty() ? config_.model_endpoint : models_.active_endpoint;

    ImGui::Columns(2, "model_stack_summary", false);
    TextMuted("Active model");
    TextColor(active_model.empty() ? "Not configured" : active_model, Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Provider API");
    TextColor(active_api.empty() ? "unknown" : active_api, Rgba(246, 248, 251));
    ImGui::NextColumn();
    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextMuted("Endpoint");
    TextColor(active_endpoint.empty() ? "Not configured" : Shorten(active_endpoint, 72), Rgba(246, 248, 251));
    ImGui::NextColumn();
    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextMuted("Router");
    TextColor(models_.router_enabled ? "Enabled" : "Planned", models_.router_enabled ? Rgba(38, 221, 123) : Rgba(205, 154, 82));
    ImGui::Columns(1);

    if (!models_.message.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextMuted(models_.message);
    }

    ImGui::Separator();
    TextColor("Discovered Models", Rgba(246, 248, 251));
    ImGui::Dummy(ImVec2(0.0f, 4.0f));

    if (models_.models.empty()) {
        TextMuted("No model inventory has been loaded yet. Refresh the runtime or check the backend model server.");
    } else if (ImGui::BeginTable("model_inventory_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 78.0f);
        ImGui::TableSetupColumn("Model");
        ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 128.0f);
        ImGui::TableSetupColumn("Caps", ImGuiTableColumnFlags_WidthFixed, 190.0f);
        ImGui::TableSetupColumn("Size", ImGuiTableColumnFlags_WidthFixed, 84.0f);
        ImGui::TableSetupColumn("Use", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableSetupColumn("Message", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableHeadersRow();

        for (int model_index = 0; model_index < static_cast<int>(models_.models.size()); ++model_index) {
            const ModelInfo& model = models_.models[model_index];
            ImGui::PushID(model_index);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const bool good = model.ready && model.available;
            Pill(model.configured ? "Active" : (good ? "Ready" : "Offline"), model.configured || good ? StatusColor(true) : StatusColor(false));
            ImGui::TableSetColumnIndex(1);
            TextColor(model.name.empty() ? model.id : model.name, model.configured ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(model.provider.empty() ? model.api : model.provider);
            ImGui::TableSetColumnIndex(3);
            TextMuted(CapabilitySummary(model.capabilities));
            ImGui::TableSetColumnIndex(4);
            TextMuted(FormatModelBytes(model.size));
            ImGui::TableSetColumnIndex(5);
            ImGui::BeginDisabled(busy_ || model.configured || Trim(model.name.empty() ? model.id : model.name).empty());
            if (ImGui::Button("Use", ImVec2(-1.0f, 0.0f))) {
                SelectModelFromInventory(model);
            }
            ImGui::EndDisabled();
            ImGui::TableSetColumnIndex(6);
            TextMuted(model.message.empty() ? "-" : Shorten(model.message, 88));
            ImGui::PopID();
        }

        ImGui::EndTable();
    }

    ImGui::Separator();
    TextColor("Provider Registry", Rgba(246, 248, 251));
    TextMuted(model_registry_.message.empty()
        ? "Provider registry will appear after the backend refreshes to the latest code."
        : model_registry_.message);
    if (ImGui::Button("New Provider")) {
        HydrateModelProviderEditor(nullptr, -1);
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(!show_model_provider_editor_);
    if (ImGui::Button("Close Editor")) {
        show_model_provider_editor_ = false;
        selected_model_provider_index_ = -1;
    }
    ImGui::EndDisabled();
    if (model_registry_.providers.empty()) {
        TextMuted("No registry providers are loaded yet.");
    } else if (ImGui::BeginTable("model_registry_provider_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Provider");
        ImGui::TableSetupColumn("API", ImGuiTableColumnFlags_WidthFixed, 110.0f);
        ImGui::TableSetupColumn("Target", ImGuiTableColumnFlags_WidthFixed, 86.0f);
        ImGui::TableSetupColumn("Roles", ImGuiTableColumnFlags_WidthFixed, 180.0f);
        ImGui::TableSetupColumn("Notes");
        ImGui::TableSetupColumn("Edit", ImGuiTableColumnFlags_WidthFixed, 70.0f);
        ImGui::TableHeadersRow();
        for (int i = 0; i < static_cast<int>(model_registry_.providers.size()); ++i) {
            const ModelRegistryProviderInfo& provider = model_registry_.providers[i];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            Pill(provider.configured ? "Active" : (provider.enabled ? "Ready" : "Planned"),
                 provider.configured ? Rgba(38, 221, 123) : (provider.enabled ? Rgba(205, 154, 82) : Rgba(133, 146, 161)));
            ImGui::TableSetColumnIndex(1);
            TextColor(provider.label.empty() ? provider.id : provider.label, provider.configured ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(provider.api.empty() ? "-" : provider.api);
            ImGui::TableSetColumnIndex(3);
            TextMuted(provider.local ? "Local" : "Cloud");
            ImGui::TableSetColumnIndex(4);
            TextMuted(Shorten(JoinPalette(provider.roles), 42));
            ImGui::TableSetColumnIndex(5);
            TextMuted(provider.notes.empty() ? provider.health : Shorten(provider.notes, 72));
            ImGui::TableSetColumnIndex(6);
            if (ImGui::Button(selected_model_provider_index_ == i && show_model_provider_editor_ ? "Editing" : "Edit", ImVec2(-1.0f, 0.0f))) {
                HydrateModelProviderEditor(&provider, i);
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    if (show_model_provider_editor_) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor(selected_model_provider_index_ >= 0 ? "Edit Provider" : "New Provider", Rgba(246, 248, 251));
        TextMuted("Add local, cloud, creative, search, embedding, judge, or audio providers here. API keys should stay in environment variables or OS credential storage.");
        ImGui::Columns(2, "model_provider_editor_columns", false);
        ImGui::InputText("Provider Id", provider_id_buffer_.data(), provider_id_buffer_.size());
        ImGui::InputText("Label", provider_label_buffer_.data(), provider_label_buffer_.size());
        ImGui::InputText("API", provider_api_buffer_.data(), provider_api_buffer_.size());
        ImGui::NextColumn();
        ImGui::InputText("Endpoint", provider_endpoint_buffer_.data(), provider_endpoint_buffer_.size());
        ImGui::InputText("Health", provider_health_buffer_.data(), provider_health_buffer_.size());
        ImGui::Checkbox("Local provider", &model_provider_local_);
        ImGui::SameLine();
        ImGui::Checkbox("Enabled", &model_provider_enabled_);
        ImGui::SameLine();
        ImGui::Checkbox("Configured", &model_provider_configured_);
        ImGui::Columns(1);
        ImGui::InputText("Capabilities", provider_capabilities_buffer_.data(), provider_capabilities_buffer_.size());
        ImGui::InputText("Roles", provider_roles_buffer_.data(), provider_roles_buffer_.size());
        ImGui::InputTextMultiline("Notes", provider_notes_buffer_.data(), provider_notes_buffer_.size(), ImVec2(-1.0f, 64.0f));

        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Save Provider")) {
            SaveModelProviderFromEditor();
        }
        ImGui::SameLine();
        const bool can_delete_provider = selected_model_provider_index_ >= 0 &&
            selected_model_provider_index_ < static_cast<int>(model_registry_.providers.size()) &&
            model_registry_.providers[selected_model_provider_index_].id != model_registry_.active_provider_id;
        ImGui::BeginDisabled(!can_delete_provider);
        if (ImGui::Button("Delete Provider")) {
            DeleteSelectedModelProvider();
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        if (ImGui::Button("Reset New")) {
            HydrateModelProviderEditor(nullptr, -1);
        }
        ImGui::EndDisabled();
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Routing Roles", Rgba(246, 248, 251));
    if (model_registry_.roles.empty()) {
        TextMuted("No routing roles are loaded yet.");
    } else if (ImGui::BeginTable("model_registry_role_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 142.0f);
        ImGui::TableSetupColumn("Primary");
        ImGui::TableSetupColumn("Fallbacks", ImGuiTableColumnFlags_WidthFixed, 118.0f);
        ImGui::TableSetupColumn("Privacy", ImGuiTableColumnFlags_WidthFixed, 108.0f);
        ImGui::TableSetupColumn("Purpose");
        ImGui::TableHeadersRow();
        for (int i = 0; i < static_cast<int>(model_registry_.roles.size()); ++i) {
            const ModelRegistryRoleInfo& role = model_registry_.roles[i];
            const bool active = Lower(role.status) == "active";
            const bool planned = Lower(role.status) == "planned";
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            Pill(active ? "Active" : (planned ? "Planned" : "Needs"),
                 active ? Rgba(38, 221, 123) : (planned ? Rgba(205, 154, 82) : Rgba(248, 113, 113)));
            ImGui::TableSetColumnIndex(1);
            TextColor(role.label.empty() ? role.id : role.label, active ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(role.primary_model.empty() ? "-" : Shorten(role.primary_model, 42));
            ImGui::TableSetColumnIndex(3);
            TextMuted(role.fallback_models.empty() ? "-" : Shorten(JoinPalette(role.fallback_models), 30));
            ImGui::TableSetColumnIndex(4);
            TextMuted(role.privacy_mode.empty() ? "local-first" : role.privacy_mode);
            ImGui::TableSetColumnIndex(5);
            TextMuted(Shorten(role.description, 82));
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Routing Presets", Rgba(246, 248, 251));
    if (model_registry_.presets.empty()) {
        TextMuted("No routing presets are loaded yet.");
    } else if (ImGui::BeginTable("model_registry_preset_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Preset", ImGuiTableColumnFlags_WidthFixed, 124.0f);
        ImGui::TableSetupColumn("Privacy", ImGuiTableColumnFlags_WidthFixed, 112.0f);
        ImGui::TableSetupColumn("Route Order");
        ImGui::TableSetupColumn("Description");
        ImGui::TableHeadersRow();
        for (int i = 0; i < static_cast<int>(model_registry_.presets.size()); ++i) {
            const ModelRoutingPresetInfo& preset = model_registry_.presets[i];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextColor(preset.label.empty() ? preset.id : preset.label, Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(1);
            TextMuted(preset.privacy_mode.empty() ? "local-first" : preset.privacy_mode);
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(JoinPalette(preset.role_order), 64));
            ImGui::TableSetColumnIndex(3);
            TextMuted(Shorten(preset.description, 82));
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    ImGui::Separator();
    TextColor("Next Router Targets", Rgba(246, 248, 251));
    const char* targets[] = {
        "Add editable model registry CRUD for local and cloud providers.",
        "Execute fallback chains so failed model calls recover automatically.",
        "Wire live task routing: chat, code, reasoning, research, vision, creative, embeddings, judge.",
        "Track latency, errors, tokens, and estimated cost per model.",
        "Connect privacy presets to actual send-time provider consent."
    };
    for (const char* target : targets) {
        ImGui::BulletText("%s", target);
    }
}

void AegisChatApp::RenderRoadmapModal()
{
    TextColor("Aegis Build Queue", Rgba(246, 248, 251));
    TextMuted("This is the in-app version of the master TODO: what we absolutely need, what needs improvement, and the bigger suggestions that make this feel like a premium AI command center.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (ImGui::Button("Open Master TODO")) {
        OpenExternalPath(ProjectDirectoryFromExecutable() / "PROJECT_TODO.md");
    }
    ImGui::SameLine();
    if (ImGui::Button("Refresh Runtime")) {
        RefreshRuntime(false);
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Settings")) {
        ImGui::OpenPopup("Aegis Settings");
        status_ = "Settings contain backend, model, workspace, and command controls.";
    }

    ImGui::Separator();
    ImGui::Columns(4, "roadmap_scoreboard", false);
    TextMuted("Desktop");
    TextColor("Stability + polish", Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Models");
    TextColor("Registry + router", Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Creative");
    TextColor("Studio + jobs", Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Learning");
    TextColor("Memory + evals", Rgba(246, 248, 251));
    ImGui::Columns(1);
    ImGui::Separator();

    if (ImGui::BeginTabBar("roadmap_tabs")) {
        if (ImGui::BeginTabItem("Absolutely Needed")) {
            const char* const desktop[] = {
                "Never open to a black window or crash from ImGui cursor/window misuse.",
                "Keep login, loading, dashboard, settings, and modals centered and readable.",
                "Preserve frameless resize, drag, minimize, maximize, and close behavior.",
                "Add persistent crash/error banners for backend, model, and render startup failures.",
                "Add screenshot smoke tests for login, loading, and dashboard."
            };
            const char* const model[] = {
                "Done: model registry foundation exposes providers, roles, and routing presets.",
                "Done: desktop model selection from live inventory.",
                "Route by task: chat, code, reasoning, research, vision, creative, embeddings, judge, and fallback.",
                "Add fallback chains so one bad model does not kill the response.",
                "Track latency, errors, tokens, and cost estimates."
            };
            const char* const chat[] = {
                "Done: retry/regenerate last response with the selected model without duplicating the user turn.",
                "Done: desktop-side cancel guard for active chat responses; backend cancellation tokens come next.",
                "Add streaming responses.",
                "Done: local conversation library with generated titles, search, pin, archive, load, and delete.",
                "Done: export the current conversation as a Markdown transcript.",
                "Done: show which model answered each assistant message.",
                "Preserve partial responses when generation fails.",
                "Done: show a cloud-context warning before workspace context goes to non-local providers.",
                "Done: context preview shows model target, attachments, workspace files, last context, and memory signals."
            };
            const char* const creative[] = {
                "Add a desktop Creative Studio job browser.",
                "Preview generated images, GIFs, animations, PSD packages, video edit plans, and beat previews.",
                "Wire revise-last with previous media job ids.",
                "Add theme, palette, aspect ratio, duration, FPS, size, and output controls.",
                "Add provider adapters for real image, video, music/audio, speech, and stem generation."
            };

            TextColor("P0 Desktop Stability", Rgba(38, 221, 123));
            for (const char* item : desktop) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("P0 Model Foundation", Rgba(38, 221, 123));
            for (const char* item : model) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("P0 Chat Experience", Rgba(38, 221, 123));
            for (const char* item : chat) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("P0 Creative Workflow", Rgba(38, 221, 123));
            for (const char* item : creative) {
                ImGui::BulletText("%s", item);
            }
            ImGui::EndTabItem();
        }

        if (ImGui::BeginTabItem("Improvements")) {
            const char* const ux[] = {
                "Add command palette and keyboard shortcuts for send, search, settings, stop, regenerate, attach, and tools.",
                "Expand the first-run Setup Check into a full guided repair flow.",
                "Add status toasts for saved settings, model failures, backend startup, media jobs, and validation.",
                "Make copy/open buttons work for message text, file paths, generated assets, commands, and logs.",
                "Done: attach selected workspace text files into the next chat message.",
                "Add drag-and-drop file attachments."
            };
            const char* const polish[] = {
                "Match goal.png colors and spacing as the base dashboard theme.",
                "Keep green accent usage intentional: active nav, primary actions, composer, online status, and progress.",
                "Avoid green borders around every card.",
                "Add consistent hover, press, disabled, loading, selected, and modal backdrop states.",
                "Clip and wrap long model names, paths, and task titles cleanly."
            };
            const char* const backend[] = {
                "Add streaming, cancellation, conversation CRUD, media job list/detail, validation profile, and checkpoint browser endpoints.",
                "Add provider-specific rate limit, quota, and structured error handling.",
                "Add hybrid retrieval: keyword plus vector embeddings.",
                "Done: Context Preview now scans visible send context for secrets and prompt-injection markers.",
                "Done: checkpoint browser endpoint lists restore points and affected files.",
                "Add backend endpoint and creative manifest smoke tests."
            };

            TextColor("Desktop UX", Rgba(246, 248, 251));
            for (const char* item : ux) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Visual Polish", Rgba(246, 248, 251));
            for (const char* item : polish) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Backend And Context", Rgba(246, 248, 251));
            for (const char* item : backend) {
                ImGui::BulletText("%s", item);
            }
            ImGui::EndTabItem();
        }

        if (ImGui::BeginTabItem("Suggestions")) {
            const char* const strategy[] = {
                "Compete on routing, speed, reliability, privacy controls, and UX rather than only model count.",
                "Add fast, balanced, best, and local-only routing presets.",
                "Add model comparison mode, then synthesize and judge the final answer.",
                "Add specialist roles for coding, code review, research, vision, creative, embeddings, and judge models.",
                "Add model eval dashboard for quality, speed, cost, and reliability."
            };
            const char* const creative[] = {
                "Build a full Creative Studio: images, video, video editing, GIFs, animation, PSD, thumbnails, icon packs, brand kits, and beats.",
                "Add before/after revision viewer and branchable creative directions.",
                "Add creative critique for composition, readability, color, pacing, export readiness, and brand fit.",
                "Add MIDI/stem plans, WAV previews, sound design notes, and mix/master guidance.",
                "Add MP4/WebM export through ffmpeg once the local package browser is stable."
            };
            const char* const learning[] = {
                "Add Teach Aegis panel for rules, preferences, and project facts.",
                "Record user likes, dislikes, revisions, rejections, and accepted code changes.",
                "Add education mode with study plans, quizzes, flashcards, and step-by-step tutoring.",
                "Add knowledge import for documents, repos, generated assets, and saved notes.",
                "Add privacy controls for local-only, project-only, and cloud-allowed memory."
            };

            TextColor("Multi-Model Strategy", Rgba(205, 154, 82));
            for (const char* item : strategy) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Creative Studio", Rgba(205, 154, 82));
            for (const char* item : creative) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Learning Engine", Rgba(205, 154, 82));
            for (const char* item : learning) {
                ImGui::BulletText("%s", item);
            }
            ImGui::EndTabItem();
        }

        if (ImGui::BeginTabItem("Execution")) {
            const char* const sprint1[] = {
                "Done: black-window startup fix, ImGui assertion fix, centered login, dashboard cleanup, model inventory modal.",
                "Done: screenshot smoke test, first-run setup diagnostics, and live inventory model selection."
            };
            const char* const sprint2[] = {
                "Backend streaming endpoint.",
                "Desktop streaming renderer.",
                "Done: desktop stop/cancel button that suppresses stale response writes.",
                "Done: retry/regenerate last answer with selected model.",
                "Done: local conversation restore, Markdown export, and desktop conversation browser."
            };
            const char* const sprint3[] = {
                "Registry storage and API.",
                "Done: desktop model selection from live inventory.",
                "Desktop registry editor.",
                "Provider adapter interface.",
                "Routing policy and fallback chain."
            };
            const char* const sprint4[] = {
                "Media job list/detail endpoints.",
                "Desktop Creative Studio browser.",
                "Preview thumbnails, beat previews, revise UI, and asset open/export buttons."
            };
            const char* const sprint5[] = {
                "Diff viewer and selective apply.",
                "Validation profile UI.",
                "Checkpoint browser, rollback, and repair loop UI."
            };

            TextColor("Sprint 1: Desktop Trust And Model Visibility", Rgba(38, 221, 123));
            for (const char* item : sprint1) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Sprint 2: Conversation And Streaming", Rgba(246, 248, 251));
            for (const char* item : sprint2) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Sprint 3: Model Router", Rgba(246, 248, 251));
            for (const char* item : sprint3) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Sprint 4: Creative Studio UI", Rgba(246, 248, 251));
            for (const char* item : sprint4) {
                ImGui::BulletText("%s", item);
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Sprint 5: Coding Workflow Upgrade", Rgba(246, 248, 251));
            for (const char* item : sprint5) {
                ImGui::BulletText("%s", item);
            }
            ImGui::EndTabItem();
        }
        ImGui::EndTabBar();
    }
}

void AegisChatApp::RenderCreativeStudioModal()
{
    if (!playing_audio_path_.empty() && !IsAudioPreviewPlaying()) {
        playing_audio_path_.clear();
    }

    TextColor("Creative Studio", Rgba(246, 248, 251));
    TextMuted("Browse generated image, video, animation, GIF, PSD, video-edit, and beat packages. Jobs keep manifests, assets, prompts, palettes, and revision history so feedback can build on prior work.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (ImGui::Button("Refresh Jobs")) {
        RefreshMediaJobs();
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Exports")) {
        std::error_code ec;
        const std::filesystem::path exports = CreativeExportDirectory();
        std::filesystem::create_directories(exports, ec);
        OpenExternalPath(exports);
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(!has_selected_media_job_ || selected_media_job_.job_dir.empty());
    if (ImGui::Button("Open Job Folder")) {
        OpenExternalPath(std::filesystem::path(Utf8ToWide(selected_media_job_.job_dir)));
    }
    ImGui::SameLine();
    if (ImGui::Button("Export Package")) {
        ExportSelectedMediaJob();
    }
    ImGui::SameLine();
    if (ImGui::Button("Use For Revision")) {
        last_media_job_id_ = selected_media_job_.id;
        last_media_kind_ = selected_media_job_.kind;
        status_ = "Revision base set to " + selected_media_job_.id + ".";
    }
    ImGui::EndDisabled();
    if (has_selected_media_job_) {
        const std::string media_feedback_payload =
            "Job: " + selected_media_job_.id +
            "\nKind: " + selected_media_job_.kind +
            "\nPrompt: " + selected_media_job_.prompt +
            "\nFeedback: " + selected_media_job_.feedback +
            "\nTheme: " + selected_media_job_.theme_color +
            "\nJob dir: " + selected_media_job_.job_dir;
        ImGui::SameLine();
        if (ImGui::Button("Copy Job Id")) {
            ImGui::SetClipboardText(selected_media_job_.id.c_str());
            status_ = "Copied Creative Studio job id.";
        }
        ImGui::SameLine();
        if (ImGui::Button("Copy Prompt")) {
            ImGui::SetClipboardText(selected_media_job_.prompt.c_str());
            status_ = "Copied Creative Studio prompt.";
        }
        ImGui::SameLine();
        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Like Job")) {
            RecordFeedback("liked", media_feedback_payload, "creative_job; job_id=" + selected_media_job_.id);
        }
        ImGui::SameLine();
        if (ImGui::Button("Reject Job")) {
            RecordFeedback("disliked", media_feedback_payload, "creative_job; job_id=" + selected_media_job_.id);
        }
        ImGui::EndDisabled();
    }

    ImGui::Separator();
    ImGui::BeginChild("creative_generation_controls", ImVec2(0.0f, 236.0f), true);
    TextColor("Generation Controls", Rgba(246, 248, 251));
    TextMuted("Create or revise media with explicit render settings.");
    ImGui::Dummy(ImVec2(0.0f, 6.0f));

    const char* media_kind_labels[] = { "Image", "Video", "Animation", "GIF", "PSD Template", "Beat", "Video Edit" };
    const char* media_kind_values[] = { "image", "video", "animation", "gif", "psd_template", "music_beat", "video_edit" };
    constexpr int media_kind_count = static_cast<int>(sizeof(media_kind_labels) / sizeof(media_kind_labels[0]));
    selected_media_kind_index_ = std::clamp(selected_media_kind_index_, 0, media_kind_count - 1);

    ImGui::PushItemWidth(178.0f);
    ImGui::Combo("Kind", &selected_media_kind_index_, media_kind_labels, media_kind_count);
    ImGui::PopItemWidth();
    ImGui::SameLine();
    ImGui::PushItemWidth(ImGui::GetContentRegionAvail().x);
    ImGui::InputTextWithHint("##creative_prompt", "Prompt", media_prompt_buffer_.data(), media_prompt_buffer_.size());
    ImGui::PopItemWidth();

    ImGui::PushItemWidth(150.0f);
    ImGui::InputTextWithHint("Theme", "auto", media_theme_buffer_.data(), media_theme_buffer_.size());
    ImGui::SameLine();
    ImGui::InputTextWithHint("Aspect", "16:9", media_aspect_ratio_buffer_.data(), media_aspect_ratio_buffer_.size());
    ImGui::SameLine();
    ImGui::SetNextItemWidth(88.0f);
    ImGui::InputInt("W", &media_width_, 0, 0);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(88.0f);
    ImGui::InputInt("H", &media_height_, 0, 0);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(98.0f);
    ImGui::SliderFloat("Seconds", &media_duration_seconds_, 0.5f, 120.0f, "%.1f");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(92.0f);
    ImGui::SliderInt("FPS", &media_fps_, 1, 60);
    ImGui::PopItemWidth();

    media_width_ = std::clamp(media_width_, 256, 4096);
    media_height_ = std::clamp(media_height_, 256, 4096);
    media_duration_seconds_ = std::clamp(media_duration_seconds_, 0.5f, 120.0f);
    media_fps_ = std::clamp(media_fps_, 1, 60);

    auto set_aspect = [&](const char* aspect, int width, int height) {
        if (ImGui::SmallButton(aspect)) {
            SetBuffer(media_aspect_ratio_buffer_, aspect);
            media_width_ = width;
            media_height_ = height;
        }
    };
    set_aspect("16:9", 1280, 720);
    ImGui::SameLine();
    set_aspect("1:1", 1080, 1080);
    ImGui::SameLine();
    set_aspect("9:16", 1080, 1920);
    ImGui::SameLine();
    set_aspect("4:5", 1080, 1350);
    if (has_selected_media_job_ && !selected_media_job_.theme_color.empty()) {
        ImGui::SameLine();
        if (ImGui::SmallButton("Use Selected Theme")) {
            SetBuffer(media_theme_buffer_, selected_media_job_.theme_color);
        }
    }

    ImGui::PushItemWidth(ImGui::GetContentRegionAvail().x * 0.48f);
    ImGui::InputTextWithHint("Style", "premium native desktop product", media_style_buffer_.data(), media_style_buffer_.size());
    ImGui::SameLine();
    ImGui::PushItemWidth(-1.0f);
    ImGui::InputTextWithHint("Formats", "auto or png, gif, html, psd, wav, mp4", media_output_formats_buffer_.data(), media_output_formats_buffer_.size());
    ImGui::PopItemWidth();
    ImGui::PopItemWidth();

    auto add_format = [&](const char* format) {
        std::vector<std::string> formats = SplitCommaList(BufferString(media_output_formats_buffer_.data()));
        if (std::find(formats.begin(), formats.end(), format) == formats.end()) {
            formats.push_back(format);
        }
        SetBuffer(media_output_formats_buffer_, JoinPalette(formats));
    };
    const char* quick_formats[] = { "png", "gif", "html", "psd", "wav", "mp4", "webm" };
    for (int i = 0; i < static_cast<int>(sizeof(quick_formats) / sizeof(quick_formats[0])); ++i) {
        if (i > 0) {
            ImGui::SameLine();
        }
        if (ImGui::SmallButton(quick_formats[i])) {
            add_format(quick_formats[i]);
        }
    }
    ImGui::SameLine();
    if (ImGui::SmallButton("Clear Formats")) {
        SetBuffer(media_output_formats_buffer_, "");
    }

    ImGui::PushItemWidth(ImGui::GetContentRegionAvail().x * 0.56f);
    ImGui::InputTextWithHint("Revision", "feedback for selected/last job", media_feedback_buffer_.data(), media_feedback_buffer_.size());
    ImGui::PopItemWidth();
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Create Package")) {
        CreateMediaJob(media_kind_values[selected_media_kind_index_], BufferString(media_prompt_buffer_.data()));
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(last_media_job_id_.empty());
    if (ImGui::Button("Revise Last")) {
        const std::string kind = last_media_kind_.empty() ? media_kind_values[selected_media_kind_index_] : last_media_kind_;
        const std::string feedback = BufferString(media_feedback_buffer_.data()).empty()
            ? BufferString(media_prompt_buffer_.data())
            : BufferString(media_feedback_buffer_.data());
        CreateMediaJob(kind, BufferString(media_prompt_buffer_.data()), feedback);
    }
    ImGui::EndDisabled();
    ImGui::EndDisabled();
    ImGui::EndChild();

    ImGui::Separator();
    const float creative_browser_height = std::max(300.0f, ImGui::GetContentRegionAvail().y);
    ImGui::BeginChild("creative_job_list", ImVec2(314.0f, creative_browser_height), true);
    TextColor("Generated Jobs", Rgba(246, 248, 251));
    TextMuted(media_jobs_.empty() ? "No jobs loaded yet. Refresh jobs or create something from the composer." : std::to_string(media_jobs_.size()) + " job(s) loaded");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    if (media_jobs_.empty()) {
        TextMuted("Create a prompt like \"make a dark trap beat\" or \"edit a launch video with captions\", then open this browser again.");
    } else {
        for (int i = 0; i < static_cast<int>(media_jobs_.size()); ++i) {
            MediaJobSummary& job = media_jobs_[i];
            const std::string title = Shorten(job.kind + " / " + job.id, 34);
            const std::string subtitle = Shorten(job.prompt.empty() ? job.created_at : job.prompt, 46);
            if (RowButton(("media_job_" + std::to_string(i)).c_str(), IconGlyph::Image, title.c_str(), subtitle.c_str(), i == selected_media_job_index_)) {
                selected_media_job_ = job;
                has_selected_media_job_ = true;
                selected_media_job_index_ = i;
                selected_media_asset_index_ = BestCreativePreviewIndex(job.assets);
                last_media_job_id_ = job.id;
                last_media_kind_ = job.kind;
            }
        }
    }
    ImGui::EndChild();

    ImGui::SameLine();
    ImGui::BeginChild("creative_job_detail", ImVec2(0.0f, creative_browser_height), true);
    if (!has_selected_media_job_) {
        TextColor("No Job Selected", Rgba(246, 248, 251));
        TextMuted("Select a Creative Studio job to inspect the prompt, plan, assets, warnings, and revision options.");
        ImGui::EndChild();
        return;
    }

    TextColor(Shorten(selected_media_job_.id, 72), Rgba(246, 248, 251));
    TextMuted(selected_media_job_.status.empty() ? "ready" : selected_media_job_.status);
    ImGui::Separator();

    ImGui::Columns(4, "creative_job_summary", false);
    TextMuted("Kind");
    TextColor(selected_media_job_.kind.empty() ? "unknown" : selected_media_job_.kind, Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Theme");
    TextColor(selected_media_job_.theme_color.empty() ? "inferred" : selected_media_job_.theme_color, Rgba(38, 221, 123));
    ImGui::NextColumn();
    TextMuted("Assets");
    TextColor(std::to_string(selected_media_job_.assets.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Created");
    TextColor(Shorten(selected_media_job_.created_at.empty() ? "unknown" : selected_media_job_.created_at, 24), Rgba(246, 248, 251));
    ImGui::Columns(1);

    if (!selected_media_job_.palette.empty() || !selected_media_job_.theme_color.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("Theme Palette", Rgba(246, 248, 251));
        const std::string palette_text = JoinPalette(selected_media_job_.palette);
        TextMuted(palette_text.empty() ? selected_media_job_.theme_color : palette_text);
        if (ImGui::Button("Copy Theme")) {
            const std::string theme = selected_media_job_.theme_color.empty() ? palette_text : selected_media_job_.theme_color;
            ImGui::SetClipboardText(theme.c_str());
            status_ = "Copied Creative Studio theme.";
        }
        ImGui::SameLine();
        ImGui::BeginDisabled(palette_text.empty());
        if (ImGui::Button("Copy Palette")) {
            ImGui::SetClipboardText(palette_text.c_str());
            status_ = "Copied Creative Studio palette.";
        }
        ImGui::EndDisabled();
    }

    if (!selected_media_job_.assets.empty()) {
        if (selected_media_asset_index_ < 0 || selected_media_asset_index_ >= static_cast<int>(selected_media_job_.assets.size())) {
            selected_media_asset_index_ = BestCreativePreviewIndex(selected_media_job_.assets);
        }
        const int preview_index = selected_media_asset_index_;
        if (preview_index >= 0 && preview_index < static_cast<int>(selected_media_job_.assets.size())) {
            const MediaAssetInfo& preview = selected_media_job_.assets[preview_index];
            const bool selected_audio = IsCreativeAudioFormat(preview.format);
            const bool selected_audio_playing = selected_audio && playing_audio_path_ == preview.path && IsAudioPreviewPlaying();
            ImGui::Dummy(ImVec2(0.0f, 10.0f));
            TextColor("Asset Preview", Rgba(246, 248, 251));
            ImGui::BeginChild("creative_asset_preview_panel", ImVec2(0.0f, 128.0f), true, ImGuiWindowFlags_NoScrollbar);
            ImDrawList* draw = ImGui::GetWindowDrawList();
            const CreativePreviewTexture* texture = GetCreativePreviewTexture(preview);
            const ImVec2 tile_size(112.0f, 100.0f);
            const ImVec2 tile_min = ImGui::GetCursorScreenPos();
            const ImVec2 tile_max(tile_min.x + tile_size.x, tile_min.y + tile_size.y);
            draw->AddRectFilled(tile_min, tile_max, Color(4, 14, 18, 0.96f), 10.0f);
            if (texture != nullptr && texture->shader_resource_view != nullptr) {
                ImVec2 image_min = tile_min;
                ImVec2 image_max = tile_max;
                if (texture->width > 0 && texture->height > 0) {
                    const float scale = std::min(tile_size.x / static_cast<float>(texture->width), tile_size.y / static_cast<float>(texture->height));
                    const ImVec2 fit_size(
                        std::max(1.0f, static_cast<float>(texture->width) * scale),
                        std::max(1.0f, static_cast<float>(texture->height) * scale));
                    image_min = ImVec2(tile_min.x + (tile_size.x - fit_size.x) * 0.5f, tile_min.y + (tile_size.y - fit_size.y) * 0.5f);
                    image_max = ImVec2(image_min.x + fit_size.x, image_min.y + fit_size.y);
                }
                const ImTextureID texture_id = static_cast<ImTextureID>(reinterpret_cast<std::uintptr_t>(texture->shader_resource_view));
                draw->AddImageRounded(texture_id, image_min, image_max, ImVec2(0.0f, 0.0f), ImVec2(1.0f, 1.0f), IM_COL32_WHITE, 10.0f);
                draw->AddRectFilled(ImVec2(tile_min.x, tile_max.y - 24.0f), tile_max, Color(4, 14, 18, 0.72f), 10.0f, ImDrawFlags_RoundCornersBottom);
            } else {
                draw->AddRectFilledMultiColor(tile_min, tile_max, Color(38, 221, 123, 0.10f), Color(80, 132, 255, 0.07f), Color(4, 14, 18, 0.0f), Color(4, 14, 18, 0.0f));
                DrawBitmapIcon(draw, CreativeAssetIcon(preview), ImVec2(tile_min.x + 34.0f, tile_min.y + 24.0f), 42.0f, Color(38, 221, 123));
            }
            draw->AddRect(tile_min, tile_max, Color(38, 221, 123, IsCreativePreviewFormat(preview.format) ? 0.48f : 0.18f), 10.0f);
            draw->AddText(ImVec2(tile_min.x + 18.0f, tile_min.y + 75.0f), Color(214, 221, 229), preview.format.empty() ? "asset" : preview.format.c_str());
            ImGui::InvisibleButton("creative_preview_tile", tile_size);
            if (ImGui::IsItemHovered()) {
                ImGui::SetTooltip("Open asset preview");
            }
            if (ImGui::IsItemClicked()) {
                OpenExternalPath(std::filesystem::path(Utf8ToWide(preview.path)));
            }

            ImGui::SameLine(0.0f, 16.0f);
            ImGui::BeginGroup();
            TextColor(CreativeAssetLabel(preview), Rgba(38, 221, 123));
            if (texture != nullptr && texture->shader_resource_view != nullptr) {
                TextMuted("Live raster preview loaded in-app.");
            } else if (selected_audio) {
                TextMuted(selected_audio_playing ? "Audio preview is playing in-app." : "Audio preview is ready to play in-app.");
            } else if (texture != nullptr && !texture->error.empty()) {
                TextMuted("Raster preview unavailable: " + texture->error);
            } else {
                TextMuted(preview.role.empty() ? "Generated Creative Studio asset" : preview.role);
            }
            TextMuted(Shorten(preview.path, 96));
            if (ImGui::Button("Open Preview")) {
                OpenExternalPath(std::filesystem::path(Utf8ToWide(preview.path)));
            }
            ImGui::SameLine();
            if (ImGui::Button("Export Preview")) {
                ExportCreativeAsset(preview);
            }
            ImGui::SameLine();
            if (ImGui::Button("Copy Preview Path")) {
                ImGui::SetClipboardText(preview.path.c_str());
                status_ = "Copied Creative Studio preview path.";
            }
            ImGui::SameLine();
            if (selected_audio) {
                if (ImGui::Button(selected_audio_playing ? "Stop Audio" : "Play Audio")) {
                    if (selected_audio_playing) {
                        StopAudioPreview();
                        playing_audio_path_.clear();
                        status_ = "Stopped Creative Studio audio preview.";
                    } else {
                        std::string error;
                        if (PlayAudioPreviewFile(std::filesystem::path(Utf8ToWide(preview.path)), &error)) {
                            playing_audio_path_ = preview.path;
                            status_ = "Playing Creative Studio audio preview.";
                        } else {
                            playing_audio_path_.clear();
                            status_ = "Audio preview failed: " + error;
                            PushToast("Audio preview failed", error, "error");
                        }
                    }
                }
                ImGui::SameLine();
            }
            if (ImGui::Button("Open Asset Folder")) {
                OpenExternalPath(std::filesystem::path(Utf8ToWide(preview.path)).parent_path());
            }
            ImGui::EndGroup();
            ImGui::EndChild();
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Prompt", Rgba(246, 248, 251));
    TextMuted(selected_media_job_.prompt.empty() ? "No prompt saved." : selected_media_job_.prompt);

    if (!selected_media_job_.plan.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("Plan", Rgba(246, 248, 251));
        for (const std::string& item : selected_media_job_.plan) {
            ImGui::BulletText("%s", item.c_str());
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Assets", Rgba(246, 248, 251));
    if (selected_media_job_.assets.empty()) {
        TextMuted("No assets were recorded for this job.");
    } else if (ImGui::BeginTable("creative_assets_table", 8, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Role");
        ImGui::TableSetupColumn("Format", ImGuiTableColumnFlags_WidthFixed, 70.0f);
        ImGui::TableSetupColumn("Path");
        ImGui::TableSetupColumn("Preview", ImGuiTableColumnFlags_WidthFixed, 74.0f);
        ImGui::TableSetupColumn("Audio", ImGuiTableColumnFlags_WidthFixed, 74.0f);
        ImGui::TableSetupColumn("Open", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableSetupColumn("Export", ImGuiTableColumnFlags_WidthFixed, 70.0f);
        ImGui::TableSetupColumn("Copy", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableHeadersRow();
        for (int i = 0; i < static_cast<int>(selected_media_job_.assets.size()); ++i) {
            const MediaAssetInfo& asset = selected_media_job_.assets[i];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(asset.role.empty() ? "asset" : Shorten(asset.role, 28));
            ImGui::TableSetColumnIndex(1);
            TextColor(asset.format.empty() ? "-" : asset.format, Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(asset.path, 72));
            ImGui::TableSetColumnIndex(3);
            if (ImGui::Button(selected_media_asset_index_ == i ? "Shown" : "Show")) {
                selected_media_asset_index_ = i;
            }
            ImGui::TableSetColumnIndex(4);
            if (IsCreativeAudioFormat(asset.format)) {
                const bool asset_playing = playing_audio_path_ == asset.path && IsAudioPreviewPlaying();
                if (ImGui::Button(asset_playing ? "Stop" : "Play")) {
                    if (asset_playing) {
                        StopAudioPreview();
                        playing_audio_path_.clear();
                        status_ = "Stopped Creative Studio audio preview.";
                    } else {
                        std::string error;
                        if (PlayAudioPreviewFile(std::filesystem::path(Utf8ToWide(asset.path)), &error)) {
                            playing_audio_path_ = asset.path;
                            status_ = "Playing Creative Studio audio preview.";
                        } else {
                            playing_audio_path_.clear();
                            status_ = "Audio preview failed: " + error;
                            PushToast("Audio preview failed", error, "error");
                        }
                    }
                }
            } else {
                TextMuted("-");
            }
            ImGui::TableSetColumnIndex(5);
            if (ImGui::Button("Open")) {
                OpenExternalPath(std::filesystem::path(Utf8ToWide(asset.path)));
            }
            ImGui::TableSetColumnIndex(6);
            if (ImGui::Button("Export")) {
                ExportCreativeAsset(asset);
            }
            ImGui::TableSetColumnIndex(7);
            if (ImGui::Button("Copy")) {
                ImGui::SetClipboardText(asset.path.c_str());
                status_ = "Copied Creative Studio asset path.";
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    if (!selected_media_job_.warnings.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("Warnings", Rgba(239, 115, 115));
        for (const std::string& warning : selected_media_job_.warnings) {
            ImGui::BulletText("%s", warning.c_str());
        }
    }

    if (!selected_media_job_.next_actions.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("Next Actions", Rgba(205, 154, 82));
        for (const std::string& action : selected_media_job_.next_actions) {
            ImGui::BulletText("%s", action.c_str());
        }
    }
    ImGui::EndChild();
}

void AegisChatApp::RenderCommandPaletteModal()
{
    TextColor("Command Palette", Rgba(246, 248, 251));
    TextMuted("Jump to the actions that matter most in the desktop app.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(10, 17, 25));
    ImGui::PushStyleColor(ImGuiCol_FrameBgHovered, Rgba(16, 25, 36));
    ImGui::PushStyleColor(ImGuiCol_FrameBgActive, Rgba(16, 30, 39));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(46, 59, 72));
    ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 8.0f);
    ImGui::PushItemWidth(-1.0f);
    if (command_palette_focus_) {
        ImGui::SetKeyboardFocusHere();
        command_palette_focus_ = false;
    }
    ImGui::InputTextWithHint("##command_palette_search", "Search actions", command_palette_buffer_.data(), command_palette_buffer_.size());
    ImGui::PopItemWidth();
    ImGui::PopStyleVar(2);
    ImGui::PopStyleColor(4);
    ImGui::Dummy(ImVec2(0.0f, 10.0f));

    const std::string filter = BufferString(command_palette_buffer_.data());
    int shown = 0;
    auto matches = [&](const std::string& title, const std::string& detail) {
        return filter.empty() || ContainsCaseInsensitive(title, filter) || ContainsCaseInsensitive(detail, filter);
    };
    auto run_and_close = [&](const std::function<void()>& action) {
        action();
        ImGui::CloseCurrentPopup();
    };
    auto command = [&](const char* id, IconGlyph icon, const std::string& title, const std::string& detail, bool enabled, const std::function<void()>& action) {
        if (!matches(title, detail)) {
            return;
        }
        ImGui::PushID(id);
        ImGui::BeginDisabled(!enabled);
        if (RowButton("command_row", icon, title.c_str(), detail.c_str(), false)) {
            run_and_close(action);
        }
        ImGui::EndDisabled();
        ImGui::PopID();
        ++shown;
    };
    const bool can_apply_selected_change =
        has_response_ &&
        !last_response_.changes.empty() &&
        !busy_ &&
        selected_change_ >= 0 &&
        selected_change_ < static_cast<int>(last_response_.changes.size()) &&
        !ChangeAlreadyApplied(last_response_, last_response_.changes[static_cast<size_t>(selected_change_)]);
    bool can_apply_selected_hunk = false;
    if (can_apply_selected_change) {
        const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
        const FileChange& change = last_response_.changes[static_cast<size_t>(selected_change_)];
        can_apply_selected_hunk = !BuildDiffHunks(BuildInlineDiffLines(change, workspace)).empty();
    }
    const bool can_fix_validation = has_response_ && ValidationFailed(last_response_) && !busy_;

    command("new_chat", IconGlyph::Plus, "New Chat", "Clear the current thread and start fresh.", true, [this]() {
        StartNewChat();
    });
    command("send", IconGlyph::Send, "Send Message", "Send the current composer text.", !busy_, [this]() {
        workspace_root_ = BufferString(workspace_buffer_.data());
        SubmitMessage();
    });
    command("cancel_generation", IconGlyph::Bolt, "Cancel Generation", "Ignore the active response when the backend call returns.", busy_ && !cancel_response_requested_, [this]() {
        CancelActiveResponse();
    });
    command("attach_selected", IconGlyph::Attach, "Attach Selected File", "Attach the currently previewed workspace text file to the next message.", has_selected_file_, [this]() {
        AttachSelectedFile();
    });
    command("context_preview", IconGlyph::Shield, "Context Preview", "Review model target, attachments, workspace files, last context, and memory signals before sending.", true, [this]() {
        pending_popup_ = "Aegis Context Preview";
        status_ = "Opened context preview.";
    });
    command("regenerate", IconGlyph::Regen, "Regenerate Last", "Ask Aegis to answer the latest user prompt again.", !busy_ && !LatestUserPrompt(history_).empty(), [this]() {
        RegenerateLastResponse();
    });
    command("retry_last", IconGlyph::Bolt, "Retry Last Message", "Retry the latest user turn without duplicating it in the transcript.", !busy_ && !LatestUserPrompt(history_).empty(), [this]() {
        RegenerateLastResponse();
    });
    command("export_conversation", IconGlyph::Copy, "Export Conversation", "Save the current chat as a Markdown transcript.", !history_.empty(), [this]() {
        ExportConversationMarkdown();
    });
    command("copy_patch", IconGlyph::Copy, "Copy Patch", "Copy the latest generated file changes as a patch package.", has_response_ && !last_response_.changes.empty(), [this]() {
        CopyPatchToClipboard();
    });
    command("export_patch", IconGlyph::Document, "Export Patch", "Save the latest generated file changes as a .patch file.", has_response_ && !last_response_.changes.empty(), [this]() {
        ExportPatchFile();
    });
    command("apply_selected_change", IconGlyph::Bolt, "Apply Selected File", "Apply only the currently selected generated file change.", can_apply_selected_change, [this]() {
        ApplySelectedChange();
    });
    command("apply_selected_hunk", IconGlyph::Bolt, "Apply Selected Hunk", "Apply only the selected diff hunk from the current generated file.", can_apply_selected_hunk, [this]() {
        ApplySelectedHunk();
    });
    command("rollback_apply", IconGlyph::Regen, "Rollback Last Apply", "Restore the latest applied file checkpoint for this workspace.", has_response_ && !last_response_.checkpoint.empty() && !busy_, [this]() {
        RollbackLastApply();
    });
    command("fix_validation", IconGlyph::Bolt, "Fix Validation", "Start a focused repair pass from the latest failing validation output.", can_fix_validation, [this]() {
        RepairLastValidationFailure();
    });
    command("checkpoints", IconGlyph::History, "Checkpoint Browser", "List workspace restore points and restore a selected checkpoint.", !busy_, [this]() {
        RefreshCheckpoints();
        pending_popup_ = "Aegis Checkpoints";
        status_ = "Opened checkpoint browser.";
    });
    command("conversations", IconGlyph::History, "Conversation Library", "Search, load, pin, archive, or delete local desktop conversations.", true, [this]() {
        RefreshConversationLibrary();
        pending_popup_ = "Aegis Conversations";
        status_ = "Opened conversations.";
    });
    command("memory_center", IconGlyph::History, "Memory Center", "Inspect, create, edit, pin, and delete workspace memory notes.", true, [this]() {
        RefreshMemoryNotes();
        pending_popup_ = "Aegis Memory Center";
        status_ = "Opened memory center.";
    });
    command("creative", IconGlyph::Image, "Creative Studio", "Open generated image, video, GIF, PSD, edit, and beat packages.", true, [this]() {
        pending_popup_ = "Aegis Creative Studio";
        RefreshMediaJobs();
    });
    command("export_creative_package", IconGlyph::Copy, "Export Creative Package", "Copy the selected Creative Studio job package into app exports.", has_selected_media_job_, [this]() {
        ExportSelectedMediaJob();
    });
    command("open_creative_exports", IconGlyph::Documents, "Open Creative Exports", "Open the local folder for exported Creative Studio assets.", true, [this]() {
        std::error_code ec;
        const std::filesystem::path exports = CreativeExportDirectory();
        std::filesystem::create_directories(exports, ec);
        OpenExternalPath(exports);
        status_ = "Opened Creative Studio exports.";
    });
    command("models", IconGlyph::Globe, "Model Stack", "Inspect active model inventory and routing readiness.", true, [this]() {
        pending_popup_ = "Aegis Model Stack";
        status_ = "Opened model stack.";
    });
    command("build_queue", IconGlyph::Document, "Build Queue", "Open the project roadmap and active TODO list.", true, [this]() {
        pending_popup_ = "Aegis Build Queue";
        status_ = "Opened the Aegis build queue.";
    });
    command("coding_routes", IconGlyph::Code, "Coding Routes", "Choose web, mobile, desktop, Linux, Windows, kernel, game, or data work.", true, [this]() {
        pending_popup_ = "Aegis Coding Routes";
        status_ = "Opened coding routes.";
    });
    command("settings", IconGlyph::Sliders, "Settings", "Edit backend, workspace, model, allowlist, and validation settings.", true, [this]() {
        pending_popup_ = "Aegis Settings";
        status_ = "Opened settings.";
    });
    command("setup_check", IconGlyph::Shield, "Setup Check", "Check backend path, Python venv/start script, model server, workspace, and validation.", true, [this]() {
        pending_popup_ = "Aegis Setup Check";
        status_ = "Opened setup check.";
    });
    command("validate", IconGlyph::Bolt, "Run Validation", "Run the saved build, test, or type-check command.", !busy_, [this]() {
        ValidateWorkspace();
    });
    command("refresh", IconGlyph::Sparkle, "Refresh Runtime", "Reload backend health, workspace files, history, and model inventory.", !busy_, [this]() {
        RefreshRuntime(false);
    });
    command("open_backend", IconGlyph::Tools, "Open Backend Folder", "Open the configured backend folder in Windows.", true, [this]() {
        OpenBackendFolder();
    });
    command("open_todo", IconGlyph::Documents, "Open Master TODO", "Open the comprehensive project checklist file.", true, [this]() {
        OpenExternalPath(ProjectDirectoryFromExecutable() / "PROJECT_TODO.md");
        status_ = "Opened master TODO.";
    });

    if (shown == 0) {
        TextMuted("No matching action.");
    }
}

void AegisChatApp::RenderToasts()
{
    if (toasts_.empty()) {
        return;
    }

    const float now = static_cast<float>(ImGui::GetTime());
    toasts_.erase(
        std::remove_if(toasts_.begin(), toasts_.end(), [now](const ToastNotification& toast) {
            return now - toast.created_at > toast.duration;
        }),
        toasts_.end());
    if (toasts_.empty()) {
        return;
    }

    ImGuiViewport* viewport = ImGui::GetMainViewport();
    ImDrawList* draw = ImGui::GetForegroundDrawList();
    constexpr float width = 352.0f;
    constexpr float height = 82.0f;
    constexpr float margin = 24.0f;
    constexpr float gap = 10.0f;

    float y = viewport->WorkPos.y + viewport->WorkSize.y - margin - height;
    const float x = viewport->WorkPos.x + viewport->WorkSize.x - margin - width;
    int visible = 0;

    for (auto it = toasts_.rbegin(); it != toasts_.rend() && visible < 4; ++it, ++visible) {
        const ToastNotification& toast = *it;
        const float age = std::max(0.0f, now - toast.created_at);
        const float fade_in = Clamp01(age / 0.22f);
        const float fade_out = Clamp01((toast.duration - age) / 0.55f);
        const float alpha = std::min(fade_in, fade_out);
        const float slide = (1.0f - EaseOutCubic(fade_in)) * 22.0f;
        const ImVec2 min(x + slide, y);
        const ImVec2 max(x + width + slide, y + height);
        const ImVec4 accent = ToastAccent(toast.tone);
        const ImU32 accent_color = ImGui::GetColorU32(ImVec4(accent.x, accent.y, accent.z, accent.w * alpha));
        const ImU32 panel = Color(9, 15, 23, 0.92f * alpha);
        const ImU32 border = Color(255, 255, 255, 0.12f * alpha);
        const ImU32 shadow = Color(0, 0, 0, 0.30f * alpha);

        draw->AddRectFilled(ImVec2(min.x, min.y + 5.0f), ImVec2(max.x, max.y + 7.0f), shadow, 12.0f);
        draw->AddRectFilled(min, max, panel, 12.0f);
        draw->AddRect(min, max, border, 12.0f, 0, 1.0f);
        draw->AddRectFilled(ImVec2(min.x, min.y), ImVec2(min.x + 4.0f, max.y), accent_color, 12.0f);
        draw->AddCircleFilled(ImVec2(min.x + 36.0f, min.y + 39.0f), 19.0f, Color(4, 18, 18, 0.92f * alpha));
        DrawBitmapIcon(draw, ToastIcon(toast.title, toast.tone), ImVec2(min.x + 24.0f, min.y + 27.0f), 24.0f, accent_color);

        draw->AddText(ImVec2(min.x + 68.0f, min.y + 16.0f), ImGui::GetColorU32(ImVec4(accent.x, accent.y, accent.z, alpha)), toast.title.c_str());
        draw->AddText(ImVec2(min.x + 68.0f, min.y + 42.0f), Color(204, 214, 225, 0.88f * alpha), Shorten(toast.message, 74).c_str());

        const float progress = Clamp01(age / toast.duration);
        draw->AddRectFilled(
            ImVec2(min.x + 68.0f, max.y - 12.0f),
            ImVec2(min.x + 68.0f + (width - 92.0f) * (1.0f - progress), max.y - 9.0f),
            accent_color,
            2.0f);

        y -= height + gap;
    }
}

void AegisChatApp::RenderCodingRoutesModal()
{
    TextColor("Coding Routes", Rgba(246, 248, 251));
    TextMuted("Pick the platform Aegis should optimize for. Routes add task-specific planning, validation, and safety posture before the agent starts working in the active workspace.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    const std::string composer_prompt = Trim(std::string(message_buffer_.data()));
    TextMuted("Current goal: " + Shorten(composer_prompt.empty() ? "Use the composer prompt or inspect the workspace for the best next coding step." : composer_prompt, 118));
    TextMuted("Workspace: " + Shorten(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_, 118));
    const std::vector<ValidationSuggestionInfo> local_suggestions = BuildProjectValidationSuggestions(files_);
    if (!local_suggestions.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        TextColor("Recommended Validation", Rgba(246, 248, 251));
        RenderValidationSuggestionTable("coding_route_validation_suggestions", local_suggestions, 5);
    } else {
        TextMuted("No validation recipe detected yet. Refresh runtime or add a saved validation profile after choosing a route.");
    }

    ImGui::Separator();
    if (ImGui::BeginTable("coding_route_grid", 2, ImGuiTableFlags_NoSavedSettings | ImGuiTableFlags_SizingStretchSame)) {
        ImGui::TableSetupColumn("left");
        ImGui::TableSetupColumn("right");
        ImGui::TableNextRow();

        ImGui::TableSetColumnIndex(0);
        if (RowButton("route_web", IconGlyph::Globe, "Web App", "Frontend, backend, APIs, responsive UI")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("web");
        }
        ImGui::Separator();
        if (RowButton("route_desktop", IconGlyph::Document, "Desktop App", "Native UX, windowing, DPI, installers")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("desktop");
        }
        ImGui::Separator();
        if (RowButton("route_macos", IconGlyph::Code, "macOS", "SwiftUI/AppKit, sandboxing, notarization")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("macos");
        }
        ImGui::Separator();
        if (RowButton("route_kernel", IconGlyph::Shield, "Kernel / System", "High-risk review-first route")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("kernel");
        }
        ImGui::Separator();
        if (RowButton("route_data", IconGlyph::Tools, "Data / Automation", "Scripts, parsers, reports, repeatable outputs")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("data");
        }
        ImGui::Separator();
        if (RowButton("route_tests", IconGlyph::Bolt, "Test Generation", "Create tests and validation coverage")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("tests");
        }

        ImGui::TableSetColumnIndex(1);
        if (RowButton("route_mobile", IconGlyph::Sparkle, "Mobile App", "React Native, Flutter, Swift, Kotlin")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("mobile");
        }
        ImGui::Separator();
        if (RowButton("route_windows", IconGlyph::Bolt, "Windows", "Win32, .NET, PowerShell, Visual Studio")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("windows");
        }
        ImGui::Separator();
        if (RowButton("route_linux", IconGlyph::Code, "Linux", "Services, packages, shell, systemd")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("linux");
        }
        ImGui::Separator();
        if (RowButton("route_game", IconGlyph::Image, "Game / Tooling", "Engines, assets, editor tools, play checks")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("game");
        }
        ImGui::Separator();
        if (RowButton("route_general", IconGlyph::Chat, "General Coding", "Inspect, plan, patch, validate")) {
            ImGui::CloseCurrentPopup();
            StartCodingRoute("general");
        }

        ImGui::EndTable();
    }

    ImGui::Separator();
    TextColor("Route Behavior", Rgba(246, 248, 251));
    ImGui::BulletText("Validation is enabled automatically so saved build/test commands can run when allowed.");
    ImGui::BulletText("Workspace file detection recommends commands for Node, Python, .NET, C++, Rust, Go, Flutter, Gradle, Swift, and Make projects.");
    ImGui::BulletText("System and kernel work starts in review mode with explicit safety checks.");
    ImGui::BulletText("The route uses your current composer text as the goal; leave it blank to let Aegis inspect the workspace first.");
}

void AegisChatApp::RenderMessage(const ChatMessage& message)
{
    const bool user = message.role == "user";
    const float available = ImGui::GetContentRegionAvail().x;
    const float card_width = std::min(user ? 720.0f : 820.0f, available * (user ? 0.74f : 0.82f));
    const float text_width = card_width - (user ? 42.0f : 112.0f);
    const ImVec2 text_size = ImGui::CalcTextSize(message.content.c_str(), nullptr, false, text_width);
    const float card_height = std::max(user ? 88.0f : 132.0f, text_size.y + (user ? 58.0f : 86.0f));

    ImGui::PushID(&message);
    if (user) {
        ImGui::SetCursorPosX(std::max(0.0f, available - card_width - 18.0f));
    } else {
        ImGui::SetCursorPosX(32.0f);
    }

    if (BeginCard(user ? "user_message" : "assistant_message", ImVec2(card_width, card_height))) {
        ImDrawList* draw = ImGui::GetWindowDrawList();
        if (user) {
            TextColor("You", Rgba(38, 221, 123));
            ImGui::SameLine(ImGui::GetWindowWidth() - 86.0f);
            TextMuted(message.time_label);
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + text_width);
            ImGui::TextWrapped("%s", message.content.c_str());
            ImGui::PopTextWrapPos();
        } else {
            const ImVec2 avatar = ImGui::GetCursorScreenPos();
            draw->AddRectFilled(avatar, ImVec2(avatar.x + 50.0f, avatar.y + 50.0f), Color(6, 13, 22), 8.0f);
            DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(avatar.x + 11.0f, avatar.y + 10.0f), 28.0f, Color(38, 221, 123));
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 66.0f);
            TextColor(config_.assistant_name.empty() ? "Aegis AI" : config_.assistant_name, Rgba(38, 221, 123));
            if (!Trim(message.model_label).empty()) {
                ImGui::SameLine();
                TextMuted("via " + Shorten(message.model_label, 34));
            }
            ImGui::SameLine(ImGui::GetWindowWidth() - 86.0f);
            TextMuted(message.time_label);
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 66.0f);
            ImGui::PushTextWrapPos(ImGui::GetCursorPosX() + text_width);
            ImGui::TextWrapped("%s", message.content.c_str());
            ImGui::PopTextWrapPos();

            const float action_y = ImGui::GetWindowHeight() - 34.0f;
            ImGui::SetCursorPos(ImVec2(66.0f, action_y));
            if (IconOnlyButton("copy_action", IconGlyph::Copy, ImVec2(24.0f, 24.0f), Rgba(0, 0, 0, 0), Rgba(25, 35, 47), Rgba(171, 181, 194))) {
                ImGui::SetClipboardText(message.content.c_str());
                status_ = "Copied response to clipboard.";
                if (!busy_) {
                    RecordMessageFeedback(message, "copied");
                }
            }
            ImGui::SameLine();
            if (IconOnlyButton("like_action", IconGlyph::Like, ImVec2(24.0f, 24.0f), Rgba(0, 0, 0, 0), Rgba(25, 35, 47), Rgba(171, 181, 194))) {
                RecordMessageFeedback(message, "liked");
            }
            ImGui::SameLine();
            if (IconOnlyButton("dislike_action", IconGlyph::Dislike, ImVec2(24.0f, 24.0f), Rgba(0, 0, 0, 0), Rgba(25, 35, 47), Rgba(171, 181, 194))) {
                RecordMessageFeedback(message, "disliked");
            }
            ImGui::SameLine();
            if (IconOnlyButton("regen_action", IconGlyph::Regen, ImVec2(24.0f, 24.0f), Rgba(0, 0, 0, 0), Rgba(25, 35, 47), Rgba(171, 181, 194))) {
                RegenerateLastResponse();
            }

            ImGui::SameLine(ImGui::GetWindowWidth() - 124.0f);
            if (IconTextButton("regenerate_action", IconGlyph::Regen, "Regenerate", ImVec2(108.0f, 34.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                RegenerateLastResponse();
            }
        }
    }
    EndCard();
    ImGui::Dummy(ImVec2(0.0f, 20.0f));
    ImGui::PopID();
}

bool AegisChatApp::ModeButton(const char* id, const char* label)
{
    const bool selected = mode_ == id;
    if (selected) {
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.20f, 0.42f, 0.39f, 1.0f));
    }
    const bool clicked = ImGui::Button(label, ImVec2(128.0f, 0.0f));
    if (selected) {
        ImGui::PopStyleColor();
    }
    return clicked;
}

}
