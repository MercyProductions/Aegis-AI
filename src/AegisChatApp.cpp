#include "AegisChatApp.h"

#include "Json.h"
#include "imgui.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstddef>
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

constexpr size_t kQueuedUserMessageLimit = 100;
constexpr int kAutopilotDefaultPassLimit = 50;
constexpr int kAutopilotMaxPassLimit = 250;

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

bool StartsWithAnyTerm(const std::string& lowered, const std::vector<std::string>& terms)
{
    for (const std::string& term : terms) {
        if (lowered.starts_with(term)) {
            return true;
        }
    }
    return false;
}

bool ContainsWindowsPathPattern(const std::string& text)
{
    for (size_t i = 0; i + 2 < text.size(); ++i) {
        const unsigned char drive = static_cast<unsigned char>(text[i]);
        if (std::isalpha(drive) && text[i + 1] == ':' && (text[i + 2] == '\\' || text[i + 2] == '/')) {
            return true;
        }
    }
    return false;
}

bool PathLooksLikeExistingProject(const std::string& path)
{
    const std::string trimmed = Trim(path);
    if (trimmed.empty()) {
        return false;
    }

    std::error_code ec;
    const std::filesystem::path root(Utf8ToWide(trimmed));
    if (!std::filesystem::exists(root, ec) || !std::filesystem::is_directory(root, ec)) {
        return false;
    }

    const std::vector<std::filesystem::path> project_markers = {
        L".aegis/project.json",
        L"package.json",
        L"pnpm-lock.yaml",
        L"yarn.lock",
        L"Cargo.toml",
        L"pyproject.toml",
        L"requirements.txt",
        L"CMakeLists.txt",
        L"Makefile",
        L"app",
        L"src",
        L"components",
        L"pages",
        L"main.cpp",
        L"main.py",
        L"DllMain.cpp",
        L"dllmain.cpp"
    };
    for (const std::filesystem::path& marker : project_markers) {
        if (std::filesystem::exists(root / marker, ec)) {
            return true;
        }
    }

    for (const auto& entry : std::filesystem::directory_iterator(root, ec)) {
        if (ec) {
            break;
        }
        if (!entry.is_regular_file(ec)) {
            continue;
        }
        const std::string extension = Lower(WideToUtf8(entry.path().extension().wstring()));
        if (extension == ".sln" || extension == ".csproj" || extension == ".vcxproj" ||
            extension == ".dll" || extension == ".lib" || extension == ".def" || extension == ".exp" || extension == ".pdb") {
            return true;
        }
    }
    return false;
}

bool PromptTargetsExistingNativeOrDllWork(const std::string& prompt)
{
    const std::string lowered = Lower(Trim(prompt));
    if (lowered.empty()) {
        return false;
    }

    const bool existing_or_refine = ContainsAnyTerm(lowered, {
        "existing", "already made", "already built", "already created", "my dll", "my library",
        "work on", "refine", "improve", "update", "fix", "debug", "repair", "clean up",
        "optimize", "continue", "make better"
    });
    const bool native_or_dll = ContainsAnyTerm(lowered, {
        "dll", "shared library", "dynamic library", "library", "native", "c++", "cpp",
        "vcxproj", "sln", "visual studio", "cmake", "minhook", "hook", "imgui", "win32",
        "windows internals", "driver"
    });
    return existing_or_refine && native_or_dll;
}

bool ShouldRouteToProjectBuilder(const std::string& prompt)
{
    const std::string lowered = Lower(Trim(prompt));
    if (lowered.empty()) {
        return false;
    }

    if (lowered.find("project builder") != std::string::npos ||
        lowered.find("scaffold") != std::string::npos ||
        lowered.find("starter project") != std::string::npos ||
        lowered.find("new project") != std::string::npos) {
        return true;
    }

    const bool creation = ContainsAnyTerm(lowered, {
        "build", "create", "generate", "make", "set up", "setup", "start",
        "complete", "finish", "build out", "flesh out", "develop", "implement", "ship"
    });
    if (!creation) {
        return false;
    }

    const bool from_scratch = ContainsAnyTerm(lowered, {
        "from scratch", "full project", "full app", "full application", "full website",
        "full site", "whole app", "whole website", "whole site", "complete project",
        "complete app", "complete website", "complete site"
    });
    const bool explicit_location = ContainsWindowsPathPattern(prompt) || ContainsAnyTerm(lowered, {
        " at this path", " at this location", " in this folder", " in this directory",
        " inside this folder", " inside this directory"
    });
    const bool question_like = StartsWithAnyTerm(lowered, {
        "how ", "what ", "why ", "where ", "when ", "who ", "which ",
        "explain ", "tell me ", "can you explain", "could you explain"
    });
    const bool explicit_create_request = ContainsAnyTerm(lowered, {
        "create", "generate", "make me", "make a", "make an", "set up", "setup",
        "implement", "complete", "finish", "write me", "write a", "write an", "build me"
    });
    if (question_like && !explicit_location && !from_scratch && !explicit_create_request) {
        return false;
    }
    if (!from_scratch && PromptTargetsExistingNativeOrDllWork(prompt)) {
        return false;
    }
    const bool project_noun = ContainsAnyTerm(lowered, {
        " project", " app", " application", " website", " web app", " api",
        " backend", " frontend", " dashboard", " cli", " command-line",
        " service", " tool", " program", " software", " executable", " exe",
        " desktop", " mobile", " game", " plugin", " extension", " bot",
        " driver", " kernel driver", " dll", " library", " shared library",
        " database", " data app"
    });
    const bool single_file_request = ContainsAnyTerm(lowered, {
        " file", " single file", " one file", " script file"
    });
    if (!(from_scratch || project_noun || (explicit_location && !single_file_request))) {
        return false;
    }

    if (!from_scratch && ContainsAnyTerm(lowered, {
            "current project", "existing project", "this project", "this app",
            "fix", "debug", "repair", "update this", "change this", "add to this"
        })) {
        return false;
    }

    return true;
}

bool IsExplicitCppProjectCreationRequest(const std::string& prompt)
{
    const std::string lowered = Lower(Trim(prompt));
    if (lowered.empty()) {
        return false;
    }

    const bool cpp_stack = ContainsAnyTerm(lowered, {
        "c++", "cpp", "cmake", "msbuild", "sln", "visual studio",
        "console app", "console project", "native app", "native project"
    });
    const bool creation = ContainsAnyTerm(lowered, {
        "build", "create", "generate", "make", "set up", "setup", "write me",
        "write a", "complete", "rebuild"
    });
    const bool concrete_output = ContainsAnyTerm(lowered, {
        "hello world", "prints hello", "print hello", "press enter",
        "user input", "console", "executable", "exe", "project", "app"
    });
    return cpp_stack && creation && concrete_output;
}

bool IsBuildOrRunFollowUp(const std::string& prompt)
{
    const std::string lowered = Lower(Trim(prompt));
    return ContainsAnyTerm(lowered, {
        "build it", "build this", "build the project", "run it", "run this",
        "compile", "compiled", "validate", "validation", "test it", "test this",
        "you didnt build", "you didn't build", "didnt build", "didn't build",
        "not built", "not build", "fix the build", "build and run", "run the app"
    });
}

bool PromptRequestsImmediateBuild(const std::string& prompt)
{
    const std::string lowered = Lower(Trim(prompt));
    return ContainsAnyTerm(lowered, {
        "also build", "and build", "build it", "build this", "build the project",
        "attempt to build", "compile it", "compile this", "run it", "run this",
        "run the app", "test it", "test this", "validate it", "validate this"
    });
}

bool WorkspaceLooksLikeCppProject(const std::string& path)
{
    const std::string trimmed = Trim(path);
    if (trimmed.empty()) {
        return false;
    }

    std::error_code ec;
    const std::filesystem::path root(Utf8ToWide(trimmed));
    if (!std::filesystem::exists(root, ec) || !std::filesystem::is_directory(root, ec)) {
        return false;
    }

    const std::vector<std::filesystem::path> markers = {
        L"CMakeLists.txt",
        L"src/main.cpp",
        L"main.cpp"
    };
    for (const std::filesystem::path& marker : markers) {
        if (std::filesystem::exists(root / marker, ec)) {
            return true;
        }
    }

    for (const auto& entry : std::filesystem::recursive_directory_iterator(root, ec)) {
        if (ec) {
            break;
        }
        if (!entry.is_regular_file(ec)) {
            continue;
        }
        const std::string extension = Lower(WideToUtf8(entry.path().extension().wstring()));
        if (extension == ".sln" || extension == ".vcxproj" || extension == ".cpp" || extension == ".cxx" || extension == ".cc") {
            return true;
        }
        if (extension == ".h" || extension == ".hpp" || extension == ".def" || extension == ".dll" || extension == ".lib") {
            return true;
        }
    }
    return false;
}

std::string DefaultValidationCommandForWorkspace(const std::string& path)
{
    const std::string trimmed = Trim(path);
    if (trimmed.empty()) {
        return {};
    }

    std::error_code ec;
    const std::filesystem::path root(Utf8ToWide(trimmed));
    if (!std::filesystem::exists(root, ec) || !std::filesystem::is_directory(root, ec)) {
        return {};
    }
    if (std::filesystem::exists(root / L"build.py", ec)) {
        return "python build.py";
    }
    if (std::filesystem::exists(root / L"CMakeLists.txt", ec)) {
        return "python build.py";
    }
    if (std::filesystem::exists(root / L"package.json", ec)) {
        std::ifstream package_file(root / L"package.json", std::ios::binary);
        const std::string package_json = package_file
            ? Lower(std::string((std::istreambuf_iterator<char>(package_file)), std::istreambuf_iterator<char>()))
            : std::string{};
        const bool uses_pnpm = std::filesystem::exists(root / L"pnpm-lock.yaml", ec);
        const bool uses_yarn = std::filesystem::exists(root / L"yarn.lock", ec);
        const std::string runner = uses_pnpm ? "pnpm" : (uses_yarn ? "yarn" : "npm");
        if (package_json.find("\"build\"") != std::string::npos) {
            return runner == "yarn" ? "yarn build" : runner + " run build";
        }
        if (package_json.find("\"test\"") != std::string::npos) {
            return runner == "npm" ? "npm test" : runner + " test";
        }
    }
    if (std::filesystem::exists(root / L"pyproject.toml", ec) ||
        std::filesystem::exists(root / L"requirements.txt", ec)) {
        if (std::filesystem::exists(root / L"tests", ec) || std::filesystem::exists(root / L"test", ec)) {
            return "python -m pytest";
        }
        return "python -m compileall .";
    }
    if (std::filesystem::exists(root / L"Cargo.toml", ec)) {
        return "cargo test";
    }
    if (std::filesystem::exists(root / L"go.mod", ec)) {
        return "go test ./...";
    }
    if (std::filesystem::exists(root / L"pom.xml", ec)) {
        return "mvn test";
    }
    if (std::filesystem::exists(root / L"build.gradle", ec) || std::filesystem::exists(root / L"build.gradle.kts", ec)) {
        return std::filesystem::exists(root / L"gradlew", ec) ? "gradlew test" : "gradle test";
    }
    for (const auto& entry : std::filesystem::directory_iterator(root, ec)) {
        if (ec) {
            break;
        }
        if (!entry.is_regular_file(ec)) {
            continue;
        }
        const std::string extension = Lower(WideToUtf8(entry.path().extension().wstring()));
        if (extension == ".sln") {
            return "msbuild \"" + WideToUtf8(entry.path().filename().wstring()) + "\" /m /p:Configuration=Release";
        }
        if (extension == ".vcxproj") {
            return "msbuild \"" + WideToUtf8(entry.path().filename().wstring()) + "\" /m /p:Configuration=Release";
        }
        if (extension == ".csproj") {
            return "dotnet build \"" + WideToUtf8(entry.path().filename().wstring()) + "\"";
        }
    }
    return {};
}

std::string BuildWorkspaceContinuityDirective(const std::string& workspace, const std::string& validation_command, bool native_project)
{
    std::ostringstream body;
    body << "Project continuity directive:\n";
    body << "- Continue the existing project in `" << workspace << "`; do not create an unrelated starter in another folder.\n";
    body << "- Preserve the detected stack, build system, and app type. Do not convert it into an unrelated template or different platform.\n";
    if (native_project) {
        body << "- Preserve the detected C++/CMake/MSBuild console-app stack. Do not replace it with a website, Python app, Node app, or generic template.\n";
    }
    body << "- Inspect the existing source, solution, project, and `.aegis` files before editing.\n";
    body << "- Build and run validation for the current project, then repair concrete compiler/build/runtime errors if any are captured.\n";
    if (!validation_command.empty()) {
        body << "- Preferred validation command: `" << validation_command << "`.\n";
        if (validation_command == "python build.py") {
            body << "- If `build.py` is missing from a C++/CMake workspace, create a portable Python build runner first; do not fall back to chained shell commands.\n";
        }
    }
    return body.str();
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
            " here ", " i want", " i need", " i'm ", " im ", " can you", " could you", " please",
            " at this path", " at this location", " in this folder", " in this directory",
            " and then ", " then ", " so ", " but ", " because ", " with ", " using ", " for me", " if ",
            " create ", " build ", " make ", " generate ", " scaffold ", " set up ", " setup ",
            " start ", " write ", " add ", " implement ", " complete ", " finish ", " develop ",
            " ship ", " update ", " modify ", " work on "
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
        "create", "build", "make", "generate", "scaffold", "write", "add", "implement",
        "set up", "setup", "complete", "finish", "build out", "flesh out", "develop", "ship"
    };
    const std::vector<std::string> artifact_terms = {
        "website", "web site", "app", "page", "file", "project", "component", "dashboard", "api", "script",
        "template", "tool", "folder", "driver", "kernel driver", "dll", "library", "shared library",
        "database", "game", "plugin", "extension", "exe", "executable", "service"
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

std::string FormatOptionalInt(int value, bool present)
{
    return present ? std::to_string(value) : "-";
}

std::string FormatCostUsd(double value, bool present)
{
    if (!present) {
        return "-";
    }

    std::ostringstream out;
    out << "$" << std::fixed << std::setprecision(value > 0.0 && value < 0.01 ? 4 : 2) << value;
    return out.str();
}

std::string FormatPercent(double value, bool present = true)
{
    if (!present) {
        return "-";
    }

    std::ostringstream out;
    out << std::fixed << std::setprecision(1) << (value * 100.0) << "%";
    return out.str();
}

std::string FormatNumber(double value, bool present = true, int precision = 1)
{
    if (!present) {
        return "-";
    }

    std::ostringstream out;
    out << std::fixed << std::setprecision(precision) << value;
    return out.str();
}

std::string JoinList(const std::vector<std::string>& values, const std::string& separator = ", ")
{
    std::ostringstream joined;
    for (size_t i = 0; i < values.size(); ++i) {
        if (i > 0) {
            joined << separator;
        }
        joined << values[i];
    }
    return joined.str();
}

bool HasAnyLoweredTerm(const std::vector<std::string>& values, const std::vector<std::string>& terms)
{
    return ContainsAnyTerm(Lower(JoinList(values, " ")), terms);
}

bool CanBenchmarkManagedModel(const ManagedModelInfo& model)
{
    if (!model.local || !model.enabled || model.provider_id.empty() || (!model.installed && !model.configured)) {
        return false;
    }
    const bool has_chat_family = HasAnyLoweredTerm(model.capabilities, {"chat", "code", "reasoning", "judge"}) ||
        HasAnyLoweredTerm(model.roles, {"chat", "code", "reasoning", "judge", "architecture", "debug", "review"});
    const bool embeddings_only = HasAnyLoweredTerm(model.capabilities, {"embedding"}) && !HasAnyLoweredTerm(model.capabilities, {"chat"});
    return has_chat_family && !embeddings_only;
}

bool HasActiveBenchmarkJob(const ModelBenchmarkSnapshot& snapshot)
{
    return std::any_of(snapshot.jobs.begin(), snapshot.jobs.end(), [](const ModelBenchmarkJobInfo& job) {
        return job.status == "queued" || job.status == "running" || job.status == "cancel_requested";
    });
}

const ModelBenchmarkJobInfo* FindBenchmarkJob(const ModelBenchmarkSnapshot& snapshot, const std::string& job_id)
{
    if (job_id.empty()) {
        return nullptr;
    }
    const auto it = std::find_if(snapshot.jobs.begin(), snapshot.jobs.end(), [&job_id](const ModelBenchmarkJobInfo& job) {
        return job.id == job_id;
    });
    return it == snapshot.jobs.end() ? nullptr : &(*it);
}

std::string FirstActiveBenchmarkJobId(const ModelBenchmarkSnapshot& snapshot)
{
    const auto it = std::find_if(snapshot.jobs.begin(), snapshot.jobs.end(), [](const ModelBenchmarkJobInfo& job) {
        return job.status == "queued" || job.status == "running" || job.status == "cancel_requested";
    });
    return it == snapshot.jobs.end() ? std::string{} : it->id;
}

std::string BenchmarkJobToastTitle(const ModelBenchmarkJobInfo& job)
{
    if (job.status == "completed") {
        return "Benchmark completed";
    }
    if (job.status == "canceled") {
        return "Benchmark canceled";
    }
    if (job.status == "failed") {
        return "Benchmark failed";
    }
    if (job.status == "interrupted") {
        return "Benchmark interrupted";
    }
    return "Benchmark updated";
}

std::string BenchmarkJobToastTone(const ModelBenchmarkJobInfo& job)
{
    if (job.status == "completed") {
        return "success";
    }
    if (job.status == "failed" || job.status == "interrupted") {
        return "error";
    }
    return "info";
}

std::vector<std::string> BenchmarkSuitesForManagedModel(const ManagedModelInfo& model)
{
    std::vector<std::string> suites;
    if (HasAnyLoweredTerm(model.capabilities, {"chat"}) || HasAnyLoweredTerm(model.roles, {"chat", "fallback"})) {
        suites.push_back("chat");
    }
    if (HasAnyLoweredTerm(model.capabilities, {"code"}) || HasAnyLoweredTerm(model.roles, {"code", "debug", "review", "refactor"})) {
        suites.push_back("code");
    }
    if (HasAnyLoweredTerm(model.capabilities, {"reasoning", "judge"}) ||
        HasAnyLoweredTerm(model.roles, {"reasoning", "architecture", "judge"})) {
        suites.push_back("reasoning");
    }
    if (suites.empty()) {
        suites.push_back("chat");
    }
    return suites;
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

std::string CompactTimestamp(const std::string& value)
{
    if (value.size() >= 19) {
        std::string stamp = value.substr(0, 19);
        std::replace(stamp.begin(), stamp.end(), 'T', ' ');
        return stamp;
    }
    return value.empty() ? "-" : value;
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

std::string BuildVerificationRepairPrompt(const VerificationResult& result)
{
    const CommandRun& failure = result.first_failure;
    const std::string output = Shorten(ValidationCombinedOutput(failure), 6000);

    std::ostringstream prompt;
    prompt << "Fix the first failing Full Verify step in this workspace. Inspect the relevant files, make the smallest safe patch, apply it, and rerun the failed command before continuing.\n\n";
    prompt << "Verification status: " << (result.status.empty() ? "unknown" : result.status) << "\n";
    prompt << "Failed command: " << (failure.command.empty() ? "[not provided]" : failure.command) << "\n";
    if (failure.has_exit_code) {
        prompt << "Exit code: " << failure.exit_code << "\n";
    }
    if (failure.timed_out) {
        prompt << "Timed out: true\n";
    }
    if (!failure.category.empty()) {
        prompt << "Failure category: " << failure.category << "\n";
    }
    if (!failure.summary.empty()) {
        prompt << "Failure summary: " << failure.summary << "\n";
    } else if (!failure.reason.empty()) {
        prompt << "Failure reason: " << failure.reason << "\n";
    }

    if (!result.steps.empty()) {
        prompt << "\nFull Verify pipeline:\n";
        const int step_count = std::min(12, static_cast<int>(result.steps.size()));
        for (int i = 0; i < step_count; ++i) {
            const VerificationStepInfo& step = result.steps[static_cast<size_t>(i)];
            prompt << "- " << (step.phase.empty() ? step.category : step.phase)
                   << " [" << (step.status.empty() ? "planned" : step.status) << "] "
                   << (step.command.empty() ? step.label : step.command);
            if (step.required) {
                prompt << " (required)";
            }
            prompt << "\n";
        }
    }

    if (!output.empty()) {
        prompt << "\nFailed command output:\n" << output << "\n";
    }
    prompt << "\nUse checkpoints and rollback if a repair attempt makes validation worse. After the failed command passes, run Full Verify again.";
    return prompt.str();
}

std::string BuildVerificationReport(
    const VerificationResult& result,
    const std::vector<VerificationRepairActivity>& activities)
{
    std::ostringstream report;
    report << "# Aegis Full Verification Report\n\n";
    report << "Workspace: " << (result.workspace_root.empty() ? "(not reported)" : result.workspace_root) << "\n";
    report << "Status: " << (result.status.empty() ? "skipped" : result.status) << "\n";
    if (!result.task_id.empty()) {
        report << "Task ID: " << result.task_id << "\n";
    }

    if (result.has_first_failure) {
        const CommandRun& failure = result.first_failure;
        report << "\n## First Failure\n\n";
        report << "Command: " << (failure.command.empty() ? "(not reported)" : failure.command) << "\n";
        if (failure.has_exit_code) {
            report << "Exit code: " << failure.exit_code << "\n";
        }
        if (!failure.category.empty()) {
            report << "Category: " << failure.category << "\n";
        }
        report << "Summary: " << (failure.summary.empty() ? failure.reason : failure.summary) << "\n";
        const std::string output = Shorten(ValidationCombinedOutput(failure), 4000);
        if (!output.empty()) {
            report << "\n```text\n" << output << "\n```\n";
        }
    }

    if (!result.steps.empty()) {
        report << "\n## Pipeline Steps\n\n";
        for (const VerificationStepInfo& step : result.steps) {
            report << "- [" << (step.status.empty() ? "planned" : step.status) << "] "
                   << (step.phase.empty() ? step.category : step.phase)
                   << " | " << (step.command.empty() ? step.label : step.command);
            if (step.required) {
                report << " | required";
            }
            std::string summary;
            if (step.has_run) {
                summary = step.run.summary.empty() ? step.run.reason : step.run.summary;
            } else {
                summary = step.reason;
            }
            if (!summary.empty()) {
                report << " | " << summary;
            }
            report << "\n";
        }
    }

    if (!activities.empty()) {
        report << "\n## Repair Activity\n\n";
        for (const VerificationRepairActivity& activity : activities) {
            report << "- " << (activity.created_at.empty() ? "--:--" : activity.created_at)
                   << " [" << (activity.status.empty() ? "info" : activity.status) << "] "
                   << (activity.title.empty() ? "Verification" : activity.title);
            if (!activity.detail.empty()) {
                report << " - " << activity.detail;
            }
            if (!activity.command.empty()) {
                report << " | " << activity.command;
            }
            report << "\n";
        }
    }

    if (!result.warnings.empty()) {
        report << "\n## Warnings\n\n";
        for (const std::string& warning : result.warnings) {
            report << "- " << warning << "\n";
        }
    }

    return report.str();
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

std::string WorkspaceProfileSearchText(const WorkspaceProjectManifestInfo& manifest)
{
    std::ostringstream text;
    text << manifest.preset_id << " "
         << manifest.preset_label << " "
         << manifest.framework << " "
         << manifest.language << " "
         << JoinPalette(manifest.tags);
    return Lower(text.str());
}

std::string SuggestedRouteForWorkspaceProfile(const WorkspaceProjectManifestInfo& manifest)
{
    const std::string text = WorkspaceProfileSearchText(manifest);
    if (text.find("mobile") != std::string::npos ||
        text.find("expo") != std::string::npos ||
        text.find("react-native") != std::string::npos ||
        text.find("react native") != std::string::npos) {
        return "mobile";
    }
    if (text.find("desktop") != std::string::npos ||
        text.find("electron") != std::string::npos ||
        text.find("tauri") != std::string::npos) {
        return "desktop";
    }
    if (text.find("windows") != std::string::npos ||
        text.find("win32") != std::string::npos) {
        return "windows";
    }
    if (text.find("web") != std::string::npos ||
        text.find("react") != std::string::npos ||
        text.find("next") != std::string::npos ||
        text.find("vite") != std::string::npos ||
        text.find("django") != std::string::npos ||
        text.find("fastapi") != std::string::npos ||
        text.find("express") != std::string::npos ||
        text.find("api") != std::string::npos) {
        return "web";
    }
    if (text.find("cli") != std::string::npos ||
        text.find("automation") != std::string::npos ||
        text.find("python") != std::string::npos ||
        text.find("rust") != std::string::npos ||
        text.find("go") != std::string::npos) {
        return "data";
    }
    return "general";
}

std::string RouteLabelForWorkspaceProfile(const std::string& route)
{
    if (route == "web") {
        return "Web Route";
    }
    if (route == "mobile") {
        return "Mobile Route";
    }
    if (route == "desktop") {
        return "Desktop Route";
    }
    if (route == "windows") {
        return "Windows Route";
    }
    if (route == "data") {
        return "Data Route";
    }
    return "Code Route";
}

std::string BuildWorkspaceFirstPassPrompt(const WorkspaceProjectManifestInfo& manifest)
{
    const std::string title = manifest.title.empty()
        ? (manifest.project_name.empty() ? "this project" : manifest.project_name)
        : manifest.title;
    std::ostringstream prompt;
    prompt << "Use the Aegis project manifest for " << title << ".\n\n"
           << "Stack: " << (manifest.framework.empty() ? "unknown" : manifest.framework)
           << " / " << (manifest.language.empty() ? "unknown" : manifest.language) << "\n";
    if (!manifest.install_command.empty()) {
        prompt << "Install command: " << manifest.install_command << "\n";
    }
    if (!manifest.validation_command.empty()) {
        prompt << "Validation command: " << manifest.validation_command << "\n";
    }
    if (!manifest.handoff_goal.empty()) {
        prompt << "Goal: " << manifest.handoff_goal << "\n";
    }
    if (!manifest.first_pass.empty()) {
        prompt << "\nFirst-pass checklist:\n";
        for (const std::string& step : manifest.first_pass) {
            prompt << "- " << step << "\n";
        }
    }
    prompt << "\nInspect the workspace, choose the safest useful first product slice, make focused changes when clear, and use the saved validation profile when validation is appropriate.";
    return prompt.str();
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

struct ProviderBlueprint {
    const char* id;
    const char* label;
    const char* api;
    const char* endpoint;
    const char* default_model;
    const char* capabilities;
    const char* roles;
    const char* env_var;
    const char* privacy;
    const char* notes;
    bool local;
};

const ProviderBlueprint kProviderBlueprints[] = {
    {
        "openai:primary",
        "OpenAI Primary",
        "openai",
        "https://api.openai.com/v1",
        "Configure in backend adapter",
        "chat, code, reasoning, research, vision, tools, structured_json, embeddings, judge",
        "chat, code, reasoning, research, vision, judge, fallback",
        "OPENAI_API_KEY",
        "cloud-allowed",
        "Use the official OpenAI SDK and Responses API in the backend adapter. Store the key in OPENAI_API_KEY or OS credential storage, never in provider notes.",
        false
    },
    {
        "anthropic:claude",
        "Anthropic Claude",
        "anthropic",
        "https://api.anthropic.com",
        "Configure in backend adapter",
        "chat, code, reasoning, tools, vision",
        "chat, code, reasoning, review, fallback",
        "ANTHROPIC_API_KEY",
        "cloud-allowed",
        "Use as a second high-quality reasoning and code-review lane. Keep provider-specific request handling in the backend adapter.",
        false
    },
    {
        "local:ollama",
        "Ollama Local",
        "ollama",
        "http://127.0.0.1:11434",
        "qwen2.5-coder:7b",
        "chat, code, embeddings",
        "chat, code, fallback",
        "",
        "local-only",
        "Local-first provider for private project context, fast drafts, offline fallback, and low-cost coding loops.",
        true
    },
    {
        "local:lmstudio",
        "LM Studio Local",
        "openai-compatible",
        "http://127.0.0.1:1234/v1",
        "Pick a loaded local model",
        "chat, code, structured_json",
        "chat, code, fallback",
        "",
        "local-only",
        "OpenAI-compatible local endpoint. Good for testing router logic without sending workspace context to the cloud.",
        true
    },
    {
        "openrouter:router",
        "OpenRouter Router",
        "openai-compatible",
        "https://openrouter.ai/api/v1",
        "Pick per route",
        "chat, code, reasoning, research, creative, vision",
        "chat, code, reasoning, research, creative, fallback",
        "OPENROUTER_API_KEY",
        "cloud-allowed",
        "Optional aggregator lane for experiments and fallback diversity. Gate private workspace context through privacy presets before sending.",
        false
    },
    {
        "perplexity:research",
        "Perplexity Research",
        "perplexity",
        "https://api.perplexity.ai",
        "Configure in backend adapter",
        "chat, research, search",
        "research, search, fallback",
        "PERPLEXITY_API_KEY",
        "cloud-allowed",
        "Specialist lane for web-grounded research answers. Keep it separate from code-editing and file-write tools.",
        false
    },
    {
        "local:judge",
        "Local Judge",
        "ollama",
        "http://127.0.0.1:11434",
        "small local evaluator",
        "chat, code, judge",
        "judge, fallback",
        "",
        "local-only",
        "Dedicated local evaluator for quick response checks, patch sanity, and private preference scoring.",
        true
    }
};

int ProviderBlueprintCount()
{
    return static_cast<int>(sizeof(kProviderBlueprints) / sizeof(kProviderBlueprints[0]));
}

const ProviderBlueprint& ModelProviderBlueprintAt(int index)
{
    return kProviderBlueprints[std::clamp(index, 0, ProviderBlueprintCount() - 1)];
}

ModelRegistryProviderInfo BuildProviderFromBlueprint(int index)
{
    const ProviderBlueprint& blueprint = ModelProviderBlueprintAt(index);
    ModelRegistryProviderInfo provider;
    provider.id = blueprint.id;
    provider.label = blueprint.label;
    provider.api = blueprint.api;
    provider.endpoint = blueprint.endpoint;
    const std::string model_hint = blueprint.default_model == nullptr ? "" : blueprint.default_model;
    provider.model_name = model_hint.find(' ') == std::string::npos ? model_hint : "";
    provider.secret_env = blueprint.env_var;
    provider.local = blueprint.local;
    provider.enabled = true;
    provider.configured = blueprint.local && !provider.model_name.empty();
    provider.capabilities = SplitCommaList(blueprint.capabilities);
    provider.roles = SplitCommaList(blueprint.roles);
    provider.cost_tier = blueprint.local ? "low" : "unknown";
    provider.health = provider.configured ? "ready" : "needs-model";

    std::ostringstream notes;
    notes << blueprint.notes;
    if (blueprint.default_model != nullptr && blueprint.default_model[0] != '\0') {
        notes << " Model hint: " << blueprint.default_model << ".";
    }
    if (blueprint.env_var != nullptr && blueprint.env_var[0] != '\0') {
        notes << " Secret env: " << blueprint.env_var << ".";
    }
    notes << " Privacy: " << blueprint.privacy << ".";
    provider.notes = notes.str();
    return provider;
}

std::string ProviderBlueprintSetupText(const ProviderBlueprint& blueprint)
{
    std::ostringstream text;
    text << blueprint.label << "\n";
    text << "Provider id: " << blueprint.id << "\n";
    text << "API: " << blueprint.api << "\n";
    text << "Endpoint: " << blueprint.endpoint << "\n";
    text << "Default model hint: " << blueprint.default_model << "\n";
    text << "Capabilities: " << blueprint.capabilities << "\n";
    text << "Roles: " << blueprint.roles << "\n";
    text << "Privacy: " << blueprint.privacy << "\n";
    if (blueprint.env_var != nullptr && blueprint.env_var[0] != '\0') {
        text << "Secret: set " << blueprint.env_var << " in the environment or OS credential storage.\n";
    } else {
        text << "Secret: none required for this local endpoint.\n";
    }
    text << "Notes: " << blueprint.notes << "\n";
    text << "Do not paste API keys into Aegis provider notes.";
    return text.str();
}

bool PaletteContainsExact(const std::vector<std::string>& values, const std::string& wanted)
{
    const std::string target = Lower(Trim(wanted));
    if (target.empty()) {
        return false;
    }
    for (const std::string& value : values) {
        if (Lower(Trim(value)) == target) {
            return true;
        }
    }
    return false;
}

struct AgentRouteBlueprint {
    const char* role;
    const char* label;
    const char* capability;
    const char* recommended;
};

const AgentRouteBlueprint kAgentRouteBlueprints[] = {
    {"chat", "Chat", "chat", "OpenAI, Claude, or local"},
    {"code", "Code", "code", "OpenAI, Claude, Ollama"},
    {"reasoning", "Reasoning", "reasoning", "OpenAI or Claude"},
    {"research", "Research", "research", "OpenAI, Perplexity, OpenRouter"},
    {"vision", "Vision", "vision", "OpenAI or Claude"},
    {"creative", "Creative", "creative", "OpenAI or OpenRouter"},
    {"embeddings", "Embeddings", "embeddings", "OpenAI or local"},
    {"judge", "Judge", "judge", "Local judge or OpenAI"},
    {"fallback", "Fallback", "chat", "Any stable enabled model"}
};

bool ProviderMatchesRoute(const ModelRegistryProviderInfo& provider, const AgentRouteBlueprint& route)
{
    return PaletteContainsExact(provider.roles, route.role) || PaletteContainsExact(provider.capabilities, route.capability);
}

int CountProvidersForRoute(const ModelRegistrySnapshot& registry, const AgentRouteBlueprint& route, bool configured_only)
{
    int count = 0;
    for (const ModelRegistryProviderInfo& provider : registry.providers) {
        if (!provider.enabled || !ProviderMatchesRoute(provider, route)) {
            continue;
        }
        if (configured_only && !provider.configured) {
            continue;
        }
        ++count;
    }
    return count;
}

std::string ProviderLabelsForRoute(const ModelRegistrySnapshot& registry, const AgentRouteBlueprint& route, bool configured_only)
{
    std::vector<std::string> labels;
    for (const ModelRegistryProviderInfo& provider : registry.providers) {
        if (!provider.enabled || !ProviderMatchesRoute(provider, route)) {
            continue;
        }
        if (configured_only && !provider.configured) {
            continue;
        }
        labels.push_back(provider.label.empty() ? provider.id : provider.label);
        if (labels.size() >= 3) {
            break;
        }
    }
    return labels.empty() ? "-" : JoinPalette(labels);
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
    if (HasNamedWorkspaceFile(files, {"build.py"})) {
        AddValidationSuggestion(suggestions, "python build.py", "Project build runner", "native/build", "Workspace build.py detected; use the project-owned configure/build/test entrypoint.");
    }
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

    if (HasNamedWorkspaceFile(files, {"CMakeLists.txt"}) && !HasNamedWorkspaceFile(files, {"build.py"})) {
        AddValidationSuggestion(suggestions, "cmake -S . -B build && cmake --build build --config Release", "CMake configure + build", "cpp", "CMake project detected; configure and build from a fresh checkout.");
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
    draw->AddRect(min, max, accent ? Color(248, 64, 82, 0.90f) : Color(44, 54, 65, 0.78f), rounding, 0, accent ? 1.5f : 1.0f);
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
    draw->AddRect(pos, max, composer ? Color(248, 64, 82, 0.42f) : Color(57, 68, 82, accent ? 0.64f : 0.58f), 14.0f, 0, composer ? 1.15f : 1.0f);
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

enum class ChromeGlyph
{
    Minimize,
    Maximize,
    Restore,
    Close
};

void DrawChromeGlyph(ImDrawList* draw, ChromeGlyph glyph, ImVec2 pos, ImVec2 size, ImU32 color)
{
    const float thickness = 1.65f;
    if (glyph == ChromeGlyph::Minimize) {
        const float y = pos.y + size.y * 0.66f;
        draw->AddLine(ImVec2(pos.x + 11.0f, y), ImVec2(pos.x + size.x - 11.0f, y), color, thickness);
        return;
    }
    if (glyph == ChromeGlyph::Maximize) {
        draw->AddRect(
            ImVec2(pos.x + 11.0f, pos.y + 8.0f),
            ImVec2(pos.x + size.x - 11.0f, pos.y + size.y - 8.0f),
            color,
            2.0f,
            0,
            thickness);
        return;
    }
    if (glyph == ChromeGlyph::Restore) {
        draw->AddRect(
            ImVec2(pos.x + 14.0f, pos.y + 7.0f),
            ImVec2(pos.x + size.x - 9.5f, pos.y + size.y - 11.0f),
            color,
            2.0f,
            0,
            thickness);
        draw->AddRectFilled(
            ImVec2(pos.x + 10.5f, pos.y + 11.0f),
            ImVec2(pos.x + size.x - 14.0f, pos.y + size.y - 7.0f),
            Color(9, 12, 18));
        draw->AddRect(
            ImVec2(pos.x + 10.5f, pos.y + 11.0f),
            ImVec2(pos.x + size.x - 14.0f, pos.y + size.y - 7.0f),
            color,
            2.0f,
            0,
            thickness);
        return;
    }

    draw->AddLine(
        ImVec2(pos.x + 11.0f, pos.y + 8.5f),
        ImVec2(pos.x + size.x - 11.0f, pos.y + size.y - 8.5f),
        color,
        thickness);
    draw->AddLine(
        ImVec2(pos.x + size.x - 11.0f, pos.y + 8.5f),
        ImVec2(pos.x + 11.0f, pos.y + size.y - 8.5f),
        color,
        thickness);
}

bool ChromeButton(const char* id, ChromeGlyph glyph, ImVec2 pos, ImVec2 size, ImVec4 hover, ImVec4 active, ImVec4 text_color)
{
    ImGui::SetCursorScreenPos(pos);
    const bool clicked = ImGui::InvisibleButton(id, size);
    const bool hovered = ImGui::IsItemHovered();
    const bool held = ImGui::IsItemActive();
    ImDrawList* draw = ImGui::GetWindowDrawList();
    if (hovered) {
        ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);
    }
    if (held) {
        draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), ImGui::GetColorU32(Rgba(50, 57, 68, 0.98f)), 8.0f);
    } else if (hovered) {
        draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), ImGui::GetColorU32(active), 6.0f);
    } else {
        draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), ImGui::GetColorU32(hover), 6.0f);
    }
    draw->AddRect(pos, ImVec2(pos.x + size.x, pos.y + size.y), Color(255, 255, 255, hovered ? 0.16f : 0.07f), 6.0f, 0, 1.0f);
    DrawChromeGlyph(draw, glyph, pos, size, ImGui::GetColorU32(text_color));
    return clicked;
}

void DrawWindowControls()
{
    const ImVec2 origin = ImGui::GetWindowPos();
    const ImVec2 window_size = ImGui::GetWindowSize();
    const float top = origin.y + 7.0f;
    const float right = origin.x + window_size.x - 12.0f;
    const ImVec2 button_size(36.0f, 30.0f);
    const ImVec4 idle = Rgba(13, 18, 25, 0.72f);
    const ChromeGlyph maximize_glyph = IsHostWindowMaximized() ? ChromeGlyph::Restore : ChromeGlyph::Maximize;

    if (ChromeButton("chrome_minimize", ChromeGlyph::Minimize, ImVec2(right - 120.0f, top), button_size, idle, Rgba(30, 39, 49, 0.98f), Rgba(215, 222, 231))) {
        RequestWindowMinimize();
    }
    if (ChromeButton("chrome_maximize", maximize_glyph, ImVec2(right - 80.0f, top), button_size, idle, Rgba(30, 39, 49, 0.98f), Rgba(215, 222, 231))) {
        RequestWindowMaximizeRestore();
    }
    if (ChromeButton("chrome_close", ChromeGlyph::Close, ImVec2(right - 40.0f, top), button_size, idle, Rgba(190, 42, 58, 0.98f), Rgba(255, 255, 255))) {
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
    const ImU32 bg = selected ? Color(68, 24, 31, 0.82f) : (hovered ? Color(32, 34, 40, 0.94f) : Color(0, 0, 0, 0));
    draw->AddRectFilled(pos, ImVec2(pos.x + size.x, pos.y + size.y), bg, 7.0f);
    if (selected) {
        const float pulse = 0.72f + Pulse(2.8f) * 0.28f;
        draw->AddRectFilled(ImVec2(pos.x, pos.y + 7.0f), ImVec2(pos.x + 3.0f, pos.y + size.y - 7.0f), Color(248, 64, 82, pulse), 2.0f);
        draw->AddRect(pos, ImVec2(pos.x + size.x, pos.y + size.y), Color(255, 255, 255, 0.055f), 7.0f);
    }
    const ImVec4 color = selected ? Rgba(255, 120, 132) : Rgba(198, 205, 213);
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
    draw->AddRectFilledMultiColor(pos, fill_max, Color(185, 28, 45), Color(248, 64, 82), Color(255, 120, 132), Color(127, 29, 39));
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

bool IsExistingProjectValidationMode(const ProjectScaffoldPlanResult& plan)
{
    return plan.execution_mode == "existing_validation"
        || plan.primary_action == "validate_existing_project";
}

bool IsExistingProjectValidationMode(const ProjectScaffoldResult& result)
{
    return result.execution_mode == "existing_validation"
        || result.primary_action == "validate_existing_project";
}

std::string ProjectBuilderModeText(bool existing_validation)
{
    return existing_validation ? "Validate existing project" : "Scaffold / update files";
}

std::string BuildProjectScaffoldChatSummary(
    const ProjectScaffoldPlanResult& plan,
    const ProjectScaffoldResult& preview)
{
    std::ostringstream summary;
    const bool existing_validation = IsExistingProjectValidationMode(plan) || IsExistingProjectValidationMode(preview);
    if (existing_validation) {
        summary << "I routed this into the Project Builder as an existing-project validation pass. No starter files are planned.\n\n";
    } else {
        summary << "I routed this into the Project Builder and prepared a safe preview. No files have been written yet.\n\n";
    }
    summary << "Mode: " << ProjectBuilderModeText(existing_validation) << "\n";
    summary << "Planned stack: " << (plan.preset.label.empty() ? plan.preset.id : plan.preset.label) << "\n";
    summary << "Project name: " << (plan.project_name.empty() ? "aegis-app" : plan.project_name) << "\n";
    summary << "Target: " << (plan.target_path.empty() ? preview.target_path : plan.target_path) << "\n";
    summary << "Files in preview: " << preview.files.size() << "\n";
    if (!plan.install_command.empty()) {
        summary << "Install: `" << plan.install_command << "`\n";
    }
    if (!plan.validation_command.empty()) {
        summary << "Validate: `" << plan.validation_command << "`\n";
    }
    if (!preview.roadmap_path.empty()) {
        summary << "Roadmap: `" << preview.roadmap_path << "`\n";
    }
    if (!plan.plan_steps.empty()) {
        summary << "\nExecution plan:\n";
        for (const std::string& step : plan.plan_steps) {
            summary << "- " << step << "\n";
        }
    }
    if (!plan.risk_warnings.empty()) {
        summary << "\nRisk notes:\n";
        for (const std::string& warning : plan.risk_warnings) {
            summary << "- " << warning << "\n";
        }
    }
    if (!preview.diff_summary.empty()) {
        summary << "\nDiff preview: " << JoinList(preview.diff_summary, ", ") << "\n";
    }
    if (!preview.stages.empty()) {
        summary << "\nVisible build plan:\n";
        for (const ProjectBuildStageInfo& stage : preview.stages) {
            summary << "- " << (stage.status.empty() ? "planned" : stage.status)
                    << ": " << (stage.label.empty() ? stage.id : stage.label);
            if (!stage.detail.empty()) {
                summary << " - " << stage.detail;
            }
            summary << "\n";
        }
    }
    if (!plan.reasons.empty()) {
        summary << "\nWhy this route:\n";
        const size_t count = std::min<size_t>(plan.reasons.size(), 3);
        for (size_t i = 0; i < count; ++i) {
            summary << "- " << plan.reasons[i] << "\n";
        }
    }
    summary << "\nThe Project Builder is open so you can inspect the plan and adjust fields. ";
    summary << (existing_validation
        ? "Click Run Validation when ready."
        : "Click Create Project when ready.");
    return summary.str();
}

std::string BuildProjectScaffoldResultSummary(const ProjectScaffoldResult& result)
{
    std::ostringstream summary;
    const bool existing_validation = IsExistingProjectValidationMode(result);
    summary << (result.message.empty() ? "Project Builder finished." : result.message) << "\n\n";
    summary << "Mode: " << ProjectBuilderModeText(existing_validation) << "\n";
    summary << "Target: " << result.target_path << "\n";
    if (result.file_change_count > 0 || !result.files.empty()) {
        summary << "File changes: " << result.file_change_count << "\n";
    } else if (existing_validation) {
        summary << "File changes: 0 (validation-only pass)\n";
    }
    if (!result.checkpoint.empty()) {
        summary << "Checkpoint: " << result.checkpoint << "\n";
    }
    if (!result.roadmap_path.empty()) {
        summary << "Roadmap: `" << result.roadmap_path << "`\n";
    }
    if (!result.diff_summary.empty()) {
        summary << "Diff: " << JoinList(result.diff_summary, ", ") << "\n";
    }
    if (!result.risk_warnings.empty()) {
        summary << "\nRisk notes handled:\n";
        for (const std::string& warning : result.risk_warnings) {
            summary << "- " << warning << "\n";
        }
    }
    if (!result.stages.empty()) {
        summary << "\nBuild loop:\n";
        for (const ProjectBuildStageInfo& stage : result.stages) {
            summary << "- " << (stage.status.empty() ? "planned" : stage.status)
                    << ": " << (stage.label.empty() ? stage.id : stage.label);
            if (!stage.detail.empty()) {
                summary << " - " << stage.detail;
            }
            summary << "\n";
        }
    }
    if (result.has_validation) {
        summary << "\nValidation: " << (ValidationPassed(result.validation) ? "passed" : "needs repair") << "\n";
        if (!result.validation.summary.empty()) {
            summary << result.validation.summary << "\n";
        }
        if (!result.validation.command.empty()) {
            summary << "Command: `" << result.validation.command << "`\n";
        }
    }
    if (!result.memory_paths.empty()) {
        summary << "\nProject memory updated:\n";
        for (const std::string& path : result.memory_paths) {
            summary << "- `" << path << "`\n";
        }
    }
    if (!result.next_steps.empty()) {
        summary << "\nNext steps:\n";
        for (const std::string& step : result.next_steps) {
            summary << "- " << step << "\n";
        }
    }
    return summary.str();
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

std::filesystem::path VerificationReportDirectory()
{
    return AppDataDirectory() / "exports" / "verification";
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

std::filesystem::path VerificationReportExportPath(const VerificationResult& result)
{
    const std::string status = SafeExportSegment(result.status.empty() ? "verification" : result.status, "verification");
    const std::string task = SafeExportSegment(result.task_id.empty() ? "task" : result.task_id, "task");
    return VerificationReportDirectory() / ("AegisVerify-" + status + "-" + task + "-" + TimestampForFileName() + ".md");
}

std::vector<std::filesystem::path> RecentVerificationReportPaths(int max_count = 5)
{
    std::vector<std::pair<std::filesystem::path, std::filesystem::file_time_type>> reports;
    std::error_code ec;
    const std::filesystem::path directory = VerificationReportDirectory();
    if (!std::filesystem::exists(directory, ec) || !std::filesystem::is_directory(directory, ec)) {
        return {};
    }

    for (const std::filesystem::directory_entry& entry : std::filesystem::directory_iterator(directory, ec)) {
        if (ec) {
            break;
        }
        if (!entry.is_regular_file(ec)) {
            continue;
        }
        const std::filesystem::path path = entry.path();
        if (Lower(WideToUtf8(path.extension().wstring())) != ".md") {
            continue;
        }
        reports.emplace_back(path, entry.last_write_time(ec));
    }

    std::sort(reports.begin(), reports.end(), [](const auto& lhs, const auto& rhs) {
        return lhs.second > rhs.second;
    });

    std::vector<std::filesystem::path> paths;
    const int count = std::min(std::max(0, max_count), static_cast<int>(reports.size()));
    paths.reserve(static_cast<size_t>(count));
    for (int i = 0; i < count; ++i) {
        paths.push_back(reports[static_cast<size_t>(i)].first);
    }
    return paths;
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

bool ConversationIsUserStartedPlaceholder(const std::vector<ChatMessage>& history);
bool ConversationIsStartupPlaceholder(const std::vector<ChatMessage>& history);

bool ConversationTitleLooksDefault(const std::string& title)
{
    const std::string trimmed = Trim(title);
    return trimmed.empty() ||
        trimmed == "New Aegis Chat" ||
        ContainsCaseInsensitive(trimmed, "Aegis desktop is ready") ||
        ContainsCaseInsensitive(trimmed, "Connect the backend") ||
        ContainsCaseInsensitive(trimmed, "New chat started");
}

bool ConversationTitleShouldRefresh(const std::string& title, const std::vector<ChatMessage>& history)
{
    (void)history;
    return ConversationTitleLooksDefault(title);
}

std::string ConversationTitleFromHistory(const std::vector<ChatMessage>& history)
{
    if (ConversationIsUserStartedPlaceholder(history) || ConversationIsStartupPlaceholder(history)) {
        return "New Aegis Chat";
    }
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
    if (ConversationIsUserStartedPlaceholder(history)) {
        return "Ready for the first prompt.";
    }
    if (ConversationIsStartupPlaceholder(history)) {
        return "Ready for the first task.";
    }
    for (auto it = history.rbegin(); it != history.rend(); ++it) {
        if (!Trim(it->content).empty()) {
            return Shorten(Trim(it->content), 120);
        }
    }
    return "No messages yet.";
}

bool ConversationHasUserMessage(const std::vector<ChatMessage>& history)
{
    return std::any_of(history.begin(), history.end(), [](const ChatMessage& message) {
        return message.role == "user" && !Trim(message.content).empty();
    });
}

bool ConversationIsUserStartedPlaceholder(const std::vector<ChatMessage>& history)
{
    if (history.size() != 1) {
        return false;
    }
    const ChatMessage& message = history.front();
    return message.role == "assistant" &&
        ContainsCaseInsensitive(message.content, "New chat started");
}

bool ConversationIsStartupPlaceholder(const std::vector<ChatMessage>& history)
{
    if (history.size() != 1) {
        return false;
    }
    const ChatMessage& message = history.front();
    return message.role == "assistant" &&
        ContainsCaseInsensitive(message.content, "Aegis desktop is ready") &&
        ContainsCaseInsensitive(message.content, "send me the first task");
}

bool ConversationIsStaleStartupPlaceholderPayload(const JsonValue& root, const std::vector<ChatMessage>& history)
{
    if (ConversationIsStartupPlaceholder(history)) {
        return true;
    }
    if (ConversationHasUserMessage(history)) {
        return false;
    }

    const std::string title = root["title"].AsString();
    const std::string preview = root["preview"].AsString();
    return ContainsCaseInsensitive(title, "Aegis desktop is ready") ||
        ContainsCaseInsensitive(preview, "Aegis desktop is ready") ||
        ContainsCaseInsensitive(preview, "send me the first task");
}

bool JsonBoolFieldLooksTrue(const std::string& body, const std::string& field)
{
    const std::string needle = "\"" + field + "\"";
    const size_t key = body.find(needle);
    if (key == std::string::npos) {
        return false;
    }
    const size_t colon = body.find(':', key + needle.size());
    if (colon == std::string::npos) {
        return false;
    }
    size_t cursor = colon + 1;
    while (cursor < body.size() && std::isspace(static_cast<unsigned char>(body[cursor]))) {
        ++cursor;
    }
    return body.compare(cursor, 4, "true") == 0;
}

bool RawConversationFileLooksLikeStaleStartupPlaceholder(const std::filesystem::path& path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        return false;
    }
    const std::string body((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    if (JsonBoolFieldLooksTrue(body, "pinned")) {
        return false;
    }
    if (body.find("\"role\":\"user\"") != std::string::npos ||
        body.find("\"role\": \"user\"") != std::string::npos) {
        return false;
    }
    return ContainsCaseInsensitive(body, "Aegis desktop is ready") &&
        ContainsCaseInsensitive(body, "send me the first task");
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
    const std::string stored_title = ConversationTitleShouldRefresh(title, history)
        ? ConversationTitleFromHistory(history)
        : title;
    file << "{\n";
    file << "  \"version\":2,\n";
    file << "  \"id\":" << JsonQuoted(id) << ",\n";
    file << "  \"title\":" << JsonQuoted(stored_title) << ",\n";
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

    body << "\n\nAttached file context:";
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
    SetBuffer(project_scaffold_name_buffer_, "aegis-app");
    login_status_.clear();
}

AegisChatApp::~AegisChatApp()
{
    if (active_task_.valid()) {
        active_task_.wait();
    }
    if (benchmark_poll_task_.valid()) {
        benchmark_poll_task_.wait();
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

void AegisChatApp::TickModelBenchmarkPolling(std::chrono::steady_clock::time_point now)
{
    if (benchmark_poll_task_.valid()) {
        if (benchmark_poll_task_.wait_for(std::chrono::milliseconds(0)) != std::future_status::ready) {
            return;
        }

        const bool had_active_job = HasActiveBenchmarkJob(model_benchmarks_);
        const std::string active_job_id = FirstActiveBenchmarkJobId(model_benchmarks_);
        try {
            ModelBenchmarkSnapshot benchmarks = benchmark_poll_task_.get();
            const ModelBenchmarkJobInfo* finished_job = FindBenchmarkJob(benchmarks, active_job_id);
            const bool has_finished_job = finished_job != nullptr;
            const ModelBenchmarkJobInfo finished_job_copy = has_finished_job ? *finished_job : ModelBenchmarkJobInfo{};
            model_benchmarks_ = std::move(benchmarks);
            const bool has_active_job = HasActiveBenchmarkJob(model_benchmarks_);
            if (had_active_job && !has_active_job && has_finished_job) {
                const std::string message = finished_job_copy.message.empty()
                    ? ("Benchmark job " + finished_job_copy.status + ".")
                    : finished_job_copy.message;
                PushToast(BenchmarkJobToastTitle(finished_job_copy), message, BenchmarkJobToastTone(finished_job_copy), 5.0f);
                if (status_.empty() || status_.find("Benchmark") != std::string::npos || status_.find("benchmark") != std::string::npos) {
                    status_ = message;
                }
            }
            next_benchmark_poll_ = now + (has_active_job ? std::chrono::seconds(2) : std::chrono::seconds(20));
        } catch (const std::exception&) {
            next_benchmark_poll_ = now + std::chrono::seconds(10);
        }
    }

    if (!HasActiveBenchmarkJob(model_benchmarks_) || now < next_benchmark_poll_) {
        return;
    }

    next_benchmark_poll_ = now + std::chrono::seconds(3);
    AegisClient client = client_;
    benchmark_poll_task_ = std::async(std::launch::async, [client]() mutable {
        return client.GetModelBenchmarks();
    });
}

void AegisChatApp::Tick()
{
    DrainStatusUpdates();
    DrainStreamDeltas();
    DrainAgentActivity();

    if (active_task_.valid() && active_task_.wait_for(std::chrono::milliseconds(0)) == std::future_status::ready) {
        const std::string finishing_label = busy_label_;
        Completion completion;
        try {
            completion = active_task_.get();
        } catch (const std::exception& error) {
            const std::string message = error.what();
            completion = [this, message]() {
                status_ = message;
                if (streaming_assistant_index_ >= 0 && streaming_assistant_index_ < static_cast<int>(history_.size())) {
                    ChatMessage& streamed = history_[static_cast<size_t>(streaming_assistant_index_)];
                    if (Trim(streamed.content).empty() || streamed.content == "Aegis is preparing a response...") {
                        streamed.content = "Aegis could not complete this streamed response.";
                    }
                    streamed.content += "\n\nStream stopped: " + message;
                    SaveConversationSnapshot();
                }
                streaming_assistant_index_ = -1;
                streaming_assistant_has_delta_ = false;
                streaming_preview_segment_start_ = 0;
                streaming_preview_attempt_ = 0;
            };
        }

        if (completion) {
            try {
                completion();
            } catch (const std::exception& error) {
                status_ = error.what();
                if (streaming_assistant_index_ >= 0 && streaming_assistant_index_ < static_cast<int>(history_.size())) {
                    ChatMessage& streamed = history_[static_cast<size_t>(streaming_assistant_index_)];
                    if (Trim(streamed.content).empty() || streamed.content == "Aegis is preparing a response...") {
                        streamed.content = "Aegis could not complete this streamed response.";
                    }
                    streamed.content += "\n\nStream stopped: " + std::string(error.what());
                    SaveConversationSnapshot();
                }
                streaming_assistant_index_ = -1;
                streaming_assistant_has_delta_ = false;
                streaming_preview_segment_start_ = 0;
                streaming_preview_attempt_ = 0;
            }
        }
        busy_ = false;
        busy_label_.clear();
        if (!finishing_label.empty()) {
            QueueAgentActivity("task", "Finished: " + finishing_label, "success");
        }
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

    if (!busy_ && pending_full_verify_after_repair_) {
        pending_full_verify_after_repair_ = false;
        VerifyWorkspace();
        return;
    }
    if (!busy_ && pending_verification_chain_repair_) {
        pending_verification_chain_repair_ = false;
        RepairLastValidationFailure(true);
        return;
    }
    if (!busy_) {
        AdvanceAutopilotIfReady();
        if (busy_) {
            return;
        }
    }

    TrySendQueuedUserMessage();

    TickModelBenchmarkPolling(now);

    if (!busy_ && now >= next_health_check_) {
        next_health_check_ = now + std::chrono::seconds(30);
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
    const bool show_conversation_sidebar = app_size.x >= 1260.0f;
    if (ImGui::BeginTable("app_shell", show_conversation_sidebar ? 3 : 2, ImGuiTableFlags_NoSavedSettings)) {
        ImGui::TableSetupColumn("Sidebar", ImGuiTableColumnFlags_WidthFixed, show_conversation_sidebar ? 224.0f : 276.0f);
        if (show_conversation_sidebar) {
            ImGui::TableSetupColumn("Conversations", ImGuiTableColumnFlags_WidthFixed, 262.0f);
        }
        ImGui::TableSetupColumn("Workspace", ImGuiTableColumnFlags_WidthStretch, 1.0f);
        ImGui::TableNextRow();

        ImGui::TableSetColumnIndex(0);
        RenderLeftPanel();

        int workspace_column = 1;
        if (show_conversation_sidebar) {
            ImGui::TableSetColumnIndex(1);
            RenderConversationSidebar();
            workspace_column = 2;
        }

        ImGui::TableSetColumnIndex(workspace_column);
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

    if (ImGui::BeginPopupModal("Aegis Planning History", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("planning_history_modal_body", ImVec2(900.0f, 640.0f), false);
        RenderPlanningHistoryModal();
        ImGui::EndChild();
        if (ImGui::Button("Close", ImVec2(-1.0f, 0.0f))) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (ImGui::BeginPopupModal("Aegis Policy Apply", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("policy_apply_modal_body", ImVec2(760.0f, 520.0f), false);
        RenderPolicyApplyConfirmModal();
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

    if (ImGui::BeginPopupModal("Aegis Project Builder", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::BeginChild("project_builder_modal_body", ImVec2(900.0f, 660.0f), false);
        RenderProjectBuilderModal();
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
    QueueAgentActivity("task", label, "running");

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

void AegisChatApp::QueueStatusUpdate(const std::string& status)
{
    const std::string trimmed = Trim(status);
    if (trimmed.empty()) {
        return;
    }
    std::lock_guard<std::mutex> lock(status_update_mutex_);
    pending_status_updates_.push_back(trimmed);
    QueueAgentActivity("status", trimmed, "running");
}

void AegisChatApp::DrainStatusUpdates()
{
    std::vector<std::string> updates;
    {
        std::lock_guard<std::mutex> lock(status_update_mutex_);
        updates.swap(pending_status_updates_);
    }
    if (!updates.empty()) {
        status_ = updates.back();
    }
}

void AegisChatApp::QueueStreamDelta(const StreamDeltaInfo& delta)
{
    if (delta.delta.empty() && delta.preview_action != "reset") {
        return;
    }
    std::lock_guard<std::mutex> lock(stream_delta_mutex_);
    pending_stream_deltas_.push_back(delta);
    if (!delta.message.empty()) {
        QueueAgentActivity("stream", delta.message, "running");
    }
}

void AegisChatApp::DrainStreamDeltas()
{
    std::vector<StreamDeltaInfo> deltas;
    {
        std::lock_guard<std::mutex> lock(stream_delta_mutex_);
        deltas.swap(pending_stream_deltas_);
    }
    if (deltas.empty()) {
        return;
    }
    if (streaming_assistant_index_ < 0 || streaming_assistant_index_ >= static_cast<int>(history_.size())) {
        return;
    }

    ChatMessage& message = history_[static_cast<size_t>(streaming_assistant_index_)];
    if (message.role != "assistant") {
        return;
    }
    if (!streaming_assistant_has_delta_) {
        message.content.clear();
        streaming_assistant_has_delta_ = true;
    }

    for (const StreamDeltaInfo& delta : deltas) {
        if (delta.source == "structured_reply_preview" && delta.preview_action == "reset") {
            if (streaming_preview_attempt_ == delta.preview_attempt &&
                streaming_preview_segment_start_ <= message.content.size()) {
                message.content.erase(streaming_preview_segment_start_);
            }
            streaming_preview_attempt_ = 0;
            streaming_preview_segment_start_ = message.content.size();
            status_ = delta.message.empty()
                ? "Retiring failed provider preview before trying the next route..."
                : delta.message;
            continue;
        }

        if (delta.delta.empty()) {
            continue;
        }

        if (delta.source == "structured_reply_preview" &&
            (streaming_preview_attempt_ != delta.preview_attempt || streaming_preview_attempt_ == 0)) {
            streaming_preview_attempt_ = delta.preview_attempt;
            streaming_preview_segment_start_ = message.content.size();
        }

        message.content += delta.delta;
        if (delta.source == "structured_preview_reconciliation") {
            status_ = "Reconciling streamed preview with final response...";
        } else if (delta.source == "structured_reply_preview" && !delta.provider_label.empty()) {
            status_ = "Receiving streamed preview from " + delta.provider_label;
            if (!delta.model.empty()) {
                status_ += " / " + delta.model;
            }
            status_ += "...";
        } else {
            status_ = "Receiving streamed response...";
        }
    }
}

void AegisChatApp::QueueAgentActivity(
    const std::string& type,
    const std::string& message,
    const std::string& status,
    const std::string& file_path,
    const std::string& command)
{
    const std::string trimmed = Trim(message);
    if (trimmed.empty()) {
        return;
    }

    AgentActivityEvent event;
    event.timestamp = NowTimeLabel();
    event.type = type.empty() ? "activity" : type;
    event.message = Shorten(trimmed, 220);
    event.file_path = Shorten(file_path, 160);
    event.command = Shorten(command, 160);
    event.status = status.empty() ? "running" : status;

    std::lock_guard<std::mutex> lock(agent_activity_mutex_);
    pending_agent_activity_.push_back(std::move(event));
}

void AegisChatApp::DrainAgentActivity()
{
    std::vector<AgentActivityEvent> events;
    {
        std::lock_guard<std::mutex> lock(agent_activity_mutex_);
        events.swap(pending_agent_activity_);
    }
    if (events.empty()) {
        return;
    }
    for (AgentActivityEvent& event : events) {
        agent_activity_.push_back(std::move(event));
    }
    constexpr size_t max_events = 160;
    if (agent_activity_.size() > max_events) {
        agent_activity_.erase(agent_activity_.begin(), agent_activity_.begin() + static_cast<std::ptrdiff_t>(agent_activity_.size() - max_events));
    }
}

void AegisChatApp::QueueUserMessageForRetry(
    const std::string& content,
    const std::vector<FileContent>& attachments,
    const std::string& reason)
{
    const std::string trimmed = Trim(content);
    if (trimmed.empty() && attachments.empty()) {
        return;
    }

    std::string display_content = trimmed.empty() ? "Use the attached workspace file(s) as context." : trimmed;
    if (!attachments.empty()) {
        display_content += "\n\n" + AttachmentSummary(attachments);
    }
    history_.push_back({"user", display_content + "\n\nQueued by Aegis: " + reason, NowTimeLabel()});
    queued_user_messages_.push_back({trimmed, attachments});
    if (queued_user_messages_.size() > kQueuedUserMessageLimit) {
        queued_user_messages_.erase(queued_user_messages_.begin());
    }
    attachments_.clear();
    message_buffer_.fill('\0');
    SaveConversationSnapshot();
    status_ = "Queued your message. Aegis will send it when the current operation is ready.";
    QueueAgentActivity("queue", "Queued user prompt for retry: " + Shorten(trimmed, 96), "pending");
}

void AegisChatApp::TrySendQueuedUserMessage()
{
    if (busy_ || queued_user_messages_.empty()) {
        return;
    }

    const bool backend_ready = health_.engine_ready || connection_state_ == "connected";
    if (!backend_ready) {
        return;
    }

    QueuedUserMessage queued = queued_user_messages_.front();
    queued_user_messages_.erase(queued_user_messages_.begin());
    QueueAgentActivity("queue", "Sending queued prompt now that Aegis is ready.", "running");
    const std::string content = queued.attachments.empty()
        ? queued.content
        : BuildMessageWithAttachments(queued.content, queued.attachments);
    SubmitMessage(content, false);
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
    const auto now = std::chrono::steady_clock::now();
    if (busy_ || runtime_refresh_in_flight_) {
        next_health_check_ = now + std::chrono::seconds(30);
        return;
    }
    runtime_refresh_in_flight_ = true;
    last_runtime_refresh_ = now;
    connection_state_ = health_.engine_ready ? "reconnecting" : "offline";
    connection_detail_ = allow_backend_start ? "Starting backend services." : "Checking backend health.";
    QueueAgentActivity("connection", connection_detail_, "running");

    AegisClient client = client_;
    const std::string preferred_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask(allow_backend_start ? "Connecting to Aegis backend..." : "Refreshing backend status...", [this, client, allow_backend_start, preferred_workspace]() mutable -> Completion {
        RuntimeSnapshot snapshot;
        try {
            snapshot = client.LoadRuntime(allow_backend_start, preferred_workspace);
        } catch (const std::exception& error) {
            const std::string message = error.what();
            return [this, message]() {
                runtime_refresh_in_flight_ = false;
                health_ = {};
                connection_state_ = "failed";
                connection_detail_ = message;
                status_ = message;
                QueueAgentActivity("connection", message, "failed");
            };
        }
        return [this, snapshot]() {
            runtime_refresh_in_flight_ = false;
            if (!snapshot.ok) {
                health_ = {};
                connection_state_ = "failed";
                connection_detail_ = snapshot.error.empty() ? "Backend is offline." : snapshot.error;
                status_ = snapshot.error.empty() ? "Aegis backend is offline." : snapshot.error;
                QueueAgentActivity("connection", connection_detail_, "failed");
                return;
            }
            ApplyRuntimeSnapshot(snapshot);
            connection_state_ = health_.engine_ready ? "connected" : "reconnecting";
            connection_detail_ = health_.engine_ready ? "Backend connected." : "Backend responded but the engine is still warming up.";
            status_ = "Backend connected.";
            QueueAgentActivity("connection", connection_detail_, health_.engine_ready ? "success" : "warning");
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
    conversation_search_buffer_.fill('\0');
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
    route_preview_ = {};
    has_route_preview_ = false;
    selected_change_ = 0;
    selected_hunk_ = 0;
    active_nav_ = "chat";
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
    if (ConversationTitleShouldRefresh(current_conversation_title_, history_)) {
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
    const std::filesystem::path library_path = ConversationLibraryPath(current_conversation_id_);
    if (current_conversation_pinned_ ||
        ConversationHasUserMessage(history_) ||
        ConversationIsUserStartedPlaceholder(history_)) {
        WriteConversationFile(
            library_path,
            current_conversation_id_,
            current_conversation_title_,
            current_conversation_pinned_,
            current_conversation_archived_,
            history_,
            workspace_root_,
            active_model);
    } else {
        std::error_code ec;
        std::filesystem::remove(library_path, ec);
    }
    RefreshConversationLibrary();
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

    std::error_code iterator_ec;
    for (const std::filesystem::directory_entry& entry : std::filesystem::directory_iterator(dir, iterator_ec)) {
        if (iterator_ec) {
            break;
        }
        std::error_code entry_ec;
        if (!entry.is_regular_file(entry_ec) || entry.path().extension() != L".json") {
            continue;
        }
        if (RawConversationFileLooksLikeStaleStartupPlaceholder(entry.path())) {
            std::error_code cleanup_ec;
            std::filesystem::remove(entry.path(), cleanup_ec);
            continue;
        }

        JsonValue root;
        std::vector<ChatMessage> messages;
        if (!LoadConversationFilePayload(entry.path(), &root, &messages) || messages.empty()) {
            continue;
        }
        const bool pinned = root["pinned"].AsBool(false);
        if (!pinned && ConversationIsStaleStartupPlaceholderPayload(root, messages)) {
            std::error_code cleanup_ec;
            std::filesystem::remove(entry.path(), cleanup_ec);
            continue;
        }
        if (!pinned && !ConversationHasUserMessage(messages) && !ConversationIsUserStartedPlaceholder(messages)) {
            continue;
        }

        LocalConversationSummary summary;
        summary.id = root["id"].AsString(entry.path().stem().string());
        summary.title = root["title"].AsString();
        if (ConversationTitleShouldRefresh(summary.title, messages)) {
            summary.title = ConversationTitleFromHistory(messages);
        }
        summary.preview = root["preview"].AsString();
        if (summary.preview.empty()) {
            summary.preview = ConversationPreviewFromHistory(messages);
        }
        summary.saved_at = root["saved_at"].AsString();
        summary.path = WideToUtf8(entry.path().wstring());
        summary.message_count = static_cast<int>(messages.size());
        summary.pinned = pinned;
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

void AegisChatApp::ExportVerificationReport()
{
    if (!has_verification_result_) {
        status_ = "Run Full Verify before exporting a verification report.";
        PushToast("Verification report", status_, "warning");
        return;
    }

    const std::filesystem::path path = VerificationReportExportPath(verification_result_);
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
        status_ = "Could not export verification report.";
        PushToast("Verification report failed", status_, "error");
        return;
    }

    file << BuildVerificationReport(verification_result_, verification_repair_activities_);
    file.close();

    status_ = "Exported verification report: " + WideToUtf8(path.wstring());
    PushToast("Verification report exported", WideToUtf8(path.filename().wstring()), "success");
    OpenExternalPath(path);
}

void AegisChatApp::OpenVerificationReportsFolder()
{
    std::error_code ec;
    const std::filesystem::path reports = VerificationReportDirectory();
    std::filesystem::create_directories(reports, ec);
    OpenExternalPath(reports);
    status_ = "Opened verification reports folder.";
}

void AegisChatApp::AttachVerificationReport(const std::string& path)
{
    const std::string trimmed = Trim(path);
    if (trimmed.empty()) {
        status_ = "No verification report path was provided.";
        return;
    }
    if (attachments_.size() >= 6) {
        status_ = "Attachment tray is full. Remove a file before adding a report.";
        return;
    }

    const std::filesystem::path report_path(Utf8ToWide(trimmed));
    std::error_code ec;
    if (!std::filesystem::exists(report_path, ec) || !std::filesystem::is_regular_file(report_path, ec)) {
        status_ = "Verification report file was not found.";
        PushToast("Report attach failed", status_, "error");
        return;
    }

    std::ifstream file(report_path, std::ios::binary);
    if (!file) {
        status_ = "Could not read verification report.";
        PushToast("Report attach failed", status_, "error");
        return;
    }
    std::ostringstream buffer;
    buffer << file.rdbuf();
    std::string content = buffer.str();
    if (Trim(content).empty()) {
        status_ = "Verification report is empty.";
        return;
    }

    const std::string report_text_path = WideToUtf8(report_path.wstring());
    for (const FileContent& attachment : attachments_) {
        if (attachment.path == report_text_path) {
            status_ = "Verification report is already attached.";
            return;
        }
    }

    FileContent attachment;
    attachment.workspace_root = WideToUtf8(VerificationReportDirectory().wstring());
    attachment.path = report_text_path;
    attachment.content = std::move(content);
    attachments_.push_back(std::move(attachment));
    status_ = "Attached verification report to the next message.";
    PushToast("Report attached", WideToUtf8(report_path.filename().wstring()), "success");
}

void AegisChatApp::PruneVerificationReports(int keep_count)
{
    const int keep = std::max(1, keep_count);
    const std::vector<std::filesystem::path> all_reports = RecentVerificationReportPaths(1000);
    if (static_cast<int>(all_reports.size()) <= keep) {
        status_ = "No old verification reports to prune.";
        return;
    }

    int removed = 0;
    for (int i = keep; i < static_cast<int>(all_reports.size()); ++i) {
        std::error_code ec;
        if (std::filesystem::remove(all_reports[static_cast<size_t>(i)], ec) && !ec) {
            ++removed;
        }
    }

    status_ = "Pruned " + std::to_string(removed) + " old verification report(s).";
    PushToast("Reports pruned", status_, removed > 0 ? "success" : "warning");
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
        ModelRegistrySnapshot registry;
        try {
            registry = client.GetModelRegistry();
        } catch (const std::exception& error) {
            registry.active_model = saved.model_name;
            registry.active_provider_id = saved.model_api + ":active";
            registry.message = error.what();
        }
        ModelManagerSnapshot manager;
        try {
            manager = client.GetModelManager();
        } catch (const std::exception& error) {
            manager.active_model = saved.model_name;
            manager.active_provider_id = registry.active_provider_id;
            manager.message = error.what();
        }
        std::string resolved_root;
        std::vector<WorkspaceFile> files = client.ListFiles(saved.default_workspace, client.Settings().max_files, &resolved_root);
        WorkspaceProfileInfo workspace_profile;
        bool has_workspace_profile = false;
        std::string workspace_profile_error;
        try {
            workspace_profile = client.GetWorkspaceProfile(resolved_root);
            has_workspace_profile = true;
        } catch (const std::exception& error) {
            workspace_profile_error = error.what();
        }
        std::vector<TaskSummary> tasks = client.GetHistory(resolved_root, 8);
        return [this,
                saved,
                models = std::move(models),
                registry = std::move(registry),
                manager = std::move(manager),
                resolved_root,
                files = std::move(files),
                workspace_profile = std::move(workspace_profile),
                has_workspace_profile,
                workspace_profile_error = std::move(workspace_profile_error),
                tasks = std::move(tasks)]() {
            config_ = saved;
            models_ = models;
            model_registry_ = registry;
            model_manager_ = manager;
            has_config_ = true;
            workspace_root_ = resolved_root;
            config_.default_workspace = resolved_root;
            files_ = files;
            workspace_profile_ = workspace_profile;
            has_workspace_profile_snapshot_ = has_workspace_profile;
            workspace_profile_error_ = workspace_profile_error;
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

void AegisChatApp::RefreshModelManager()
{
    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Refreshing model manager...", [this, client, workspace]() mutable {
        ModelManagerSnapshot manager = client.GetModelManager();
        ModelInventory inventory = client.GetModels();
        ModelRegistrySnapshot registry = client.GetModelRegistry();
        ModelRegistryAuditInfo audit;
        std::string audit_error;
        bool audit_loaded = false;
        try {
            audit = client.GetModelRegistryAudit(workspace);
            audit_loaded = true;
        } catch (const std::exception& error) {
            audit_error = error.what();
        }
        ModelRegistryCheckpointList checkpoints;
        std::string checkpoint_error;
        bool checkpoints_loaded = false;
        try {
            checkpoints = client.GetModelRegistryCheckpoints(8);
            checkpoints_loaded = true;
        } catch (const std::exception& error) {
            checkpoint_error = error.what();
        }
        return [this,
                manager = std::move(manager),
                inventory = std::move(inventory),
                registry = std::move(registry),
                audit = std::move(audit),
                audit_error = std::move(audit_error),
                audit_loaded,
                checkpoints = std::move(checkpoints),
                checkpoint_error = std::move(checkpoint_error),
                checkpoints_loaded]() {
            model_manager_ = manager;
            models_ = inventory;
            model_registry_ = registry;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = audit_loaded;
            model_registry_audit_error_ = audit_error;
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = checkpoints_loaded;
            model_registry_checkpoints_error_ = checkpoint_error;
            status_ = "Model manager refreshed.";
        };
    });
}

void AegisChatApp::RefreshModelBenchmarks()
{
    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Refreshing model benchmarks...", [this, client, workspace]() mutable {
        ModelBenchmarkSnapshot benchmarks = client.GetModelBenchmarks();
        ModelRegistryBenchmarkPreviewInfo preview;
        std::string preview_error;
        bool preview_loaded = false;
        try {
            preview = client.GetBenchmarkRoutePreview(workspace);
            preview_loaded = true;
        } catch (const std::exception& error) {
            preview_error = error.what();
        }
        return [this,
                benchmarks = std::move(benchmarks),
                preview = std::move(preview),
                preview_error = std::move(preview_error),
                preview_loaded]() {
            model_benchmarks_ = benchmarks;
            route_apply_preview_ = preview;
            route_apply_preview_loaded_ = preview_loaded;
            route_apply_preview_error_ = preview_error;
            status_ = "Model benchmark scores refreshed.";
        };
    });
}

void AegisChatApp::RunQuickModelBenchmarks()
{
    RunModelBenchmarkPreset("quick local model benchmark", {"chat", "code", "reasoning"}, 4, 45.0);
}

void AegisChatApp::RunModelBenchmarkPreset(
    const std::string& label,
    const std::vector<std::string>& suite_ids,
    int max_models,
    double timeout_seconds,
    const std::vector<std::string>& provider_ids)
{
    AegisClient client = client_;
    StartTask("Running " + label + "...", [this, client, label, suite_ids, max_models, timeout_seconds, provider_ids]() mutable {
        ModelBenchmarkJobInfo job = client.StartModelBenchmarkJob(suite_ids, max_models, true, timeout_seconds, provider_ids);
        ModelBenchmarkSnapshot benchmarks = client.GetModelBenchmarks();
        ModelRegistrySnapshot registry = client.GetModelRegistry();
        return [this, label, job = std::move(job), benchmarks = std::move(benchmarks), registry = std::move(registry)]() {
            model_benchmarks_ = benchmarks;
            model_registry_ = registry;
            status_ = "Started " + label + ": " + job.message;
            PushToast("Benchmark started", job.message, "info");
        };
    });
}

void AegisChatApp::RunManagedModelBenchmark(const ManagedModelInfo& model)
{
    if (!CanBenchmarkManagedModel(model)) {
        status_ = "This model is not benchmarkable yet. Use installed local chat/code/reasoning models.";
        PushToast("Benchmark blocked", status_, "warning");
        return;
    }
    const std::vector<std::string> suites = BenchmarkSuitesForManagedModel(model);
    const std::string model_name = model.name.empty() ? model.provider_id : model.name;
    RunModelBenchmarkPreset(
        "targeted benchmark for " + Shorten(model_name, 42),
        suites,
        1,
        60.0,
        {model.provider_id});
}

void AegisChatApp::CancelModelBenchmarkJob(const ModelBenchmarkJobInfo& job)
{
    const std::string job_id = Trim(job.id);
    if (job_id.empty()) {
        status_ = "Benchmark job id is missing.";
        PushToast("Cancel blocked", status_, "warning");
        return;
    }

    AegisClient client = client_;
    StartTask("Canceling benchmark job...", [this, client, job_id]() mutable {
        ModelBenchmarkJobInfo canceled = client.CancelModelBenchmarkJob(job_id);
        ModelBenchmarkSnapshot benchmarks = client.GetModelBenchmarks();
        return [this, canceled = std::move(canceled), benchmarks = std::move(benchmarks)]() {
            model_benchmarks_ = benchmarks;
            status_ = canceled.message.empty() ? "Benchmark job cancel requested." : canceled.message;
            PushToast("Benchmark cancel", status_, canceled.status == "canceled" ? "success" : "info");
        };
    });
}

void AegisChatApp::ApplyBenchmarkWinnersToRoutes()
{
    if (model_benchmarks_.provider_scores.empty()) {
        status_ = "Run benchmark scores before applying route winners.";
        PushToast("Benchmark routes", status_, "warning");
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Applying health-aware route winners...", [this, client, workspace]() mutable {
        ModelRegistrySnapshot registry = client.ApplyBenchmarkWinnersToRegistry(workspace);
        ModelRegistryAuditInfo audit = client.GetModelRegistryAudit();
        ModelBenchmarkSnapshot benchmarks = client.GetModelBenchmarks();
        ModelManagerSnapshot manager = client.GetModelManager();
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        ModelRegistryBenchmarkPreviewInfo preview;
        std::string preview_error;
        bool preview_loaded = false;
        try {
            preview = client.GetBenchmarkRoutePreview(workspace);
            preview_loaded = true;
        } catch (const std::exception& error) {
            preview_error = error.what();
        }
        return [this,
                registry = std::move(registry),
                audit = std::move(audit),
                benchmarks = std::move(benchmarks),
                manager = std::move(manager),
                checkpoints = std::move(checkpoints),
                preview = std::move(preview),
                preview_error = std::move(preview_error),
                preview_loaded]() {
            model_registry_ = registry;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = true;
            model_registry_audit_error_.clear();
            model_benchmarks_ = benchmarks;
            model_manager_ = manager;
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
            route_apply_preview_ = preview;
            route_apply_preview_loaded_ = preview_loaded;
            route_apply_preview_error_ = preview_error;
            status_ = registry.message.empty() ? "Applied health-aware benchmark winners to routing roles." : registry.message;
            PushToast("Healthy routes applied", status_, "success");
        };
    });
}

void AegisChatApp::ApplyRoutePolicyDiffToRoutes()
{
    const int role_change_count = static_cast<int>(std::count_if(
        route_policy_diff_.role_proposals.begin(),
        route_policy_diff_.role_proposals.end(),
        [](const RoutePolicyRoleProposalInfo& proposal) {
            return Lower(proposal.action) != "keep";
        }));
    const int provider_change_count = static_cast<int>(std::count_if(
        route_policy_diff_.provider_proposals.begin(),
        route_policy_diff_.provider_proposals.end(),
        [](const RoutePolicyProviderProposalInfo& proposal) {
            const std::string action = Lower(proposal.action);
            return action != "hold" && action != "monitor";
        }));
    if (!route_policy_diff_loaded_ || (role_change_count + provider_change_count) <= 0) {
        status_ = "Refresh Planning History before applying route policy changes.";
        PushToast("Policy apply", status_, "warning");
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Applying safe route policy diff...", [this, client, workspace]() mutable {
        ModelRegistrySnapshot registry = client.ApplyRoutePolicyDiffToRegistry(workspace, 200, 3, 0.55, false);
        ModelRegistryAuditInfo audit = client.GetModelRegistryAudit();
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        RoutePolicyDiffInfo policy_diff = client.GetRoutePolicyDiff(workspace, 200, 3);
        RouteQualitySnapshot route_quality = client.GetRouteQuality(workspace, 200);
        return [this,
                registry = std::move(registry),
                audit = std::move(audit),
                checkpoints = std::move(checkpoints),
                policy_diff = std::move(policy_diff),
                route_quality = std::move(route_quality)]() {
            model_registry_ = registry;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = true;
            model_registry_audit_error_.clear();
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
            route_policy_diff_ = policy_diff;
            route_policy_diff_loaded_ = true;
            route_policy_diff_error_.clear();
            route_quality_ = route_quality;
            route_quality_loaded_ = true;
            route_quality_error_.clear();
            status_ = registry.message.empty() ? "Applied safe route policy diff." : registry.message;
            PushToast("Policy applied", status_, "success");
        };
    });
}

void AegisChatApp::PullManagedModel(const ManagedModelInfo& model)
{
    const std::string model_name = Trim(model.name);
    if (model_name.empty()) {
        status_ = "Select a model with a valid name before pulling.";
        PushToast("Model pull blocked", status_, "error");
        return;
    }

    AegisClient client = client_;
    StartTask("Starting model pull: " + Shorten(model_name, 48), [this, client, model_name]() mutable {
        ModelOperationInfo operation = client.PullModel(model_name, 24.0);
        ModelManagerSnapshot manager = client.GetModelManager();
        return [this, operation = std::move(operation), manager = std::move(manager)]() {
            model_manager_ = manager;
            status_ = operation.message.empty()
                ? "Started model pull: " + operation.model_name + "."
                : operation.message + " " + operation.model_name + ".";
            PushToast("Model pull started", operation.model_name, "success");
        };
    });
}

void AegisChatApp::DeleteManagedModel(const ManagedModelInfo& model)
{
    const std::string model_name = Trim(model.name);
    if (model_name.empty()) {
        status_ = "Select a local model with a valid name before removing it.";
        PushToast("Model removal blocked", status_, "error");
        return;
    }
    if (model.active) {
        status_ = "The active model cannot be removed. Select another model first.";
        PushToast("Model removal blocked", status_, "error");
        return;
    }

    AegisClient client = client_;
    StartTask("Removing model: " + Shorten(model_name, 48), [this, client, model_name]() mutable {
        ModelOperationInfo operation = client.DeleteLocalModel(model_name);
        ModelManagerSnapshot manager = client.GetModelManager();
        ModelInventory inventory = client.GetModels();
        ModelRegistrySnapshot registry = client.GetModelRegistry();
        return [this, operation = std::move(operation), manager = std::move(manager), inventory = std::move(inventory), registry = std::move(registry)]() {
            model_manager_ = manager;
            models_ = inventory;
            model_registry_ = registry;
            status_ = operation.message.empty()
                ? "Started model removal: " + operation.model_name + "."
                : operation.message + " " + operation.model_name + ".";
            PushToast("Model removal started", operation.model_name, "warning");
        };
    });
}

void AegisChatApp::HydrateModelProviderBlueprint(int index)
{
    const ModelRegistryProviderInfo provider = BuildProviderFromBlueprint(index);
    HydrateModelProviderEditor(&provider, -1);
    selected_model_provider_index_ = -1;
    status_ = "Staged provider blueprint: " + provider.label + ".";
    PushToast("Provider blueprint staged", provider.label, "info");
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
        SetBuffer(provider_model_buffer_, "");
        SetBuffer(provider_aliases_buffer_, "");
        SetBuffer(provider_secret_env_buffer_, "");
        SetBuffer(provider_capabilities_buffer_, "chat, code");
        SetBuffer(provider_roles_buffer_, "chat, fallback");
        SetBuffer(provider_cost_tier_buffer_, "unknown");
        SetBuffer(provider_health_buffer_, "planned");
        SetBuffer(provider_notes_buffer_, "Add endpoint and model routing notes here.");
        model_provider_local_ = false;
        model_provider_enabled_ = true;
        model_provider_configured_ = false;
        model_provider_context_window_ = 0;
        model_provider_rate_limit_rpm_ = 0;
        model_provider_input_cost_per_million_ = 0.0f;
        model_provider_output_cost_per_million_ = 0.0f;
        return;
    }

    SetBuffer(provider_id_buffer_, provider->id);
    SetBuffer(provider_label_buffer_, provider->label.empty() ? provider->id : provider->label);
    SetBuffer(provider_api_buffer_, provider->api);
    SetBuffer(provider_endpoint_buffer_, provider->endpoint);
    SetBuffer(provider_model_buffer_, provider->model_name);
    SetBuffer(provider_aliases_buffer_, JoinPalette(provider->model_aliases));
    SetBuffer(provider_secret_env_buffer_, provider->secret_env);
    SetBuffer(provider_capabilities_buffer_, JoinPalette(provider->capabilities));
    SetBuffer(provider_roles_buffer_, JoinPalette(provider->roles));
    SetBuffer(provider_cost_tier_buffer_, provider->cost_tier.empty() ? "unknown" : provider->cost_tier);
    SetBuffer(provider_health_buffer_, provider->health.empty() ? "unknown" : provider->health);
    SetBuffer(provider_notes_buffer_, provider->notes);
    model_provider_local_ = provider->local;
    model_provider_enabled_ = provider->enabled;
    model_provider_configured_ = provider->configured;
    model_provider_context_window_ = provider->context_window;
    model_provider_rate_limit_rpm_ = provider->rate_limit_rpm;
    model_provider_input_cost_per_million_ = static_cast<float>(provider->input_cost_per_million);
    model_provider_output_cost_per_million_ = static_cast<float>(provider->output_cost_per_million);
}

void AegisChatApp::SaveModelProviderFromEditor()
{
    ModelRegistryProviderInfo provider;
    provider.id = BufferString(provider_id_buffer_.data());
    provider.label = BufferString(provider_label_buffer_.data());
    provider.api = BufferString(provider_api_buffer_.data());
    provider.endpoint = BufferString(provider_endpoint_buffer_.data());
    provider.model_name = BufferString(provider_model_buffer_.data());
    provider.model_aliases = SplitCommaList(BufferString(provider_aliases_buffer_.data()));
    provider.secret_env = BufferString(provider_secret_env_buffer_.data());
    provider.local = model_provider_local_;
    provider.enabled = model_provider_enabled_;
    provider.configured = model_provider_configured_;
    provider.capabilities = SplitCommaList(BufferString(provider_capabilities_buffer_.data()));
    provider.roles = SplitCommaList(BufferString(provider_roles_buffer_.data()));
    provider.cost_tier = BufferString(provider_cost_tier_buffer_.data());
    provider.context_window = std::max(0, model_provider_context_window_);
    provider.rate_limit_rpm = std::max(0, model_provider_rate_limit_rpm_);
    provider.input_cost_per_million = std::max(0.0f, model_provider_input_cost_per_million_);
    provider.output_cost_per_million = std::max(0.0f, model_provider_output_cost_per_million_);
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
        ModelRegistryAuditInfo audit = client.GetModelRegistryAudit();
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        return [this,
                saved = std::move(saved),
                audit = std::move(audit),
                checkpoints = std::move(checkpoints),
                provider_id = provider.id]() {
            model_registry_ = saved;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = true;
            model_registry_audit_error_.clear();
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
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
        ModelRegistryAuditInfo audit = client.GetModelRegistryAudit();
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        return [this,
                saved = std::move(saved),
                audit = std::move(audit),
                checkpoints = std::move(checkpoints),
                provider_id]() {
            model_registry_ = saved;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = true;
            model_registry_audit_error_.clear();
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
            show_model_provider_editor_ = false;
            selected_model_provider_index_ = -1;
            status_ = "Deleted model provider: " + provider_id + ".";
            PushToast("Provider deleted", provider_id, "success");
        };
    });
}

void AegisChatApp::CreateModelRegistryCheckpoint()
{
    AegisClient client = client_;
    StartTask("Creating model registry checkpoint...", [this, client]() mutable {
        ModelRegistryCheckpointInfo checkpoint = client.CreateModelRegistryCheckpoint(
            "Manual checkpoint from Aegis desktop before model routing changes.");
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        return [this, checkpoint = std::move(checkpoint), checkpoints = std::move(checkpoints)]() {
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
            selected_model_registry_checkpoint_diff_loaded_ = false;
            selected_model_registry_checkpoint_diff_error_.clear();
            has_pending_model_registry_restore_ = false;
            status_ = "Created model registry checkpoint: " + Shorten(checkpoint.id, 32) + ".";
            PushToast("Registry checkpoint created", checkpoint.reason.empty() ? checkpoint.id : checkpoint.reason, "success");
        };
    });
}

void AegisChatApp::LoadModelRegistryCheckpointDiff(const ModelRegistryCheckpointInfo& checkpoint)
{
    const std::string checkpoint_id = Trim(checkpoint.id);
    if (checkpoint_id.empty()) {
        status_ = "Checkpoint id is missing.";
        PushToast("Registry diff blocked", status_, "warning");
        return;
    }

    AegisClient client = client_;
    StartTask("Loading model registry checkpoint details...", [this, client, checkpoint_id]() mutable {
        ModelRegistryCheckpointDiffInfo diff = client.GetModelRegistryCheckpointDiff(checkpoint_id);
        return [this, diff = std::move(diff)]() {
            selected_model_registry_checkpoint_diff_ = diff;
            selected_model_registry_checkpoint_diff_loaded_ = true;
            selected_model_registry_checkpoint_diff_error_.clear();
            status_ = "Loaded checkpoint details: " + Shorten(selected_model_registry_checkpoint_diff_.checkpoint.id, 32) + ".";
        };
    });
}

void AegisChatApp::RequestModelRegistryCheckpointRestore(const ModelRegistryCheckpointInfo& checkpoint)
{
    const std::string checkpoint_id = Trim(checkpoint.id);
    if (checkpoint_id.empty()) {
        status_ = "Checkpoint id is missing.";
        PushToast("Registry restore blocked", status_, "warning");
        return;
    }

    pending_model_registry_restore_ = checkpoint;
    has_pending_model_registry_restore_ = true;
    const bool details_loaded =
        selected_model_registry_checkpoint_diff_loaded_ &&
        selected_model_registry_checkpoint_diff_.checkpoint.id == checkpoint_id;
    if (!details_loaded) {
        LoadModelRegistryCheckpointDiff(checkpoint);
        status_ = "Review checkpoint details, then confirm restore.";
        PushToast("Review restore", "Loaded checkpoint details before restore.", "info");
        return;
    }

    status_ = "Review checkpoint details, then confirm restore.";
    PushToast("Restore pending", "Confirm restore from checkpoint details.", "warning");
}

void AegisChatApp::RestoreModelRegistryCheckpoint(const ModelRegistryCheckpointInfo& checkpoint)
{
    const std::string checkpoint_id = Trim(checkpoint.id);
    if (checkpoint_id.empty()) {
        status_ = "Checkpoint id is missing.";
        PushToast("Registry restore blocked", status_, "warning");
        return;
    }

    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Restoring model registry checkpoint...", [this, client, checkpoint_id, workspace]() mutable {
        ModelRegistrySnapshot registry = client.RestoreModelRegistryCheckpoint(checkpoint_id);
        ModelRegistryAuditInfo audit = client.GetModelRegistryAudit();
        ModelInventory inventory = client.GetModels();
        ModelManagerSnapshot manager = client.GetModelManager();
        ModelRegistryCheckpointList checkpoints = client.GetModelRegistryCheckpoints(8);
        ModelRegistryBenchmarkPreviewInfo preview;
        std::string preview_error;
        bool preview_loaded = false;
        try {
            preview = client.GetBenchmarkRoutePreview(workspace);
            preview_loaded = true;
        } catch (const std::exception& error) {
            preview_error = error.what();
        }
        return [this,
                registry = std::move(registry),
                audit = std::move(audit),
                inventory = std::move(inventory),
                manager = std::move(manager),
                checkpoints = std::move(checkpoints),
                preview = std::move(preview),
                preview_error = std::move(preview_error),
                preview_loaded,
                checkpoint_id]() {
            model_registry_ = registry;
            model_registry_audit_ = audit;
            model_registry_audit_loaded_ = true;
            model_registry_audit_error_.clear();
            models_ = inventory;
            model_manager_ = manager;
            model_registry_checkpoints_ = checkpoints;
            model_registry_checkpoints_loaded_ = true;
            model_registry_checkpoints_error_.clear();
            route_apply_preview_ = preview;
            route_apply_preview_loaded_ = preview_loaded;
            route_apply_preview_error_ = preview_error;
            selected_model_registry_checkpoint_diff_loaded_ = false;
            selected_model_registry_checkpoint_diff_error_.clear();
            has_pending_model_registry_restore_ = false;
            status_ = registry.message.empty() ? "Restored model registry checkpoint: " + checkpoint_id + "." : registry.message;
            PushToast("Registry restored", checkpoint_id, "success");
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

void AegisChatApp::BeginAutopilotSession(const std::string& goal)
{
    autopilot_active_ = true;
    autopilot_stop_requested_ = false;
    autopilot_finishing_ = false;
    autopilot_waiting_for_result_ = true;
    autopilot_dependency_verify_attempted_ = false;
    autopilot_rounds_completed_ = 0;
    autopilot_min_rounds_ = std::max(3, autopilot_min_rounds_);
    autopilot_max_rounds_ = std::max({kAutopilotDefaultPassLimit, autopilot_min_rounds_, autopilot_max_rounds_});
    autopilot_goal_ = Shorten(Trim(goal), 1200);
    apply_changes_ = true;
    run_validation_ = true;
    project_scaffold_run_install_ = true;
    project_scaffold_run_validation_ = true;
    max_repairs_ = std::max(max_repairs_, 5);
    verification_include_install_ = true;
    verification_continue_on_failure_ = true;
    verification_auto_repair_chain_ = true;
    verification_chain_repairs_remaining_ = 0;
    RefreshAutopilotSuggestions();
    status_ = "Autopilot started. Aegis will continue until a clean stopping point or wrap-up request.";
}

void AegisChatApp::RequestAutopilotWrapUp()
{
    if (!autopilot_active_) {
        autopilot_enabled_ = false;
        status_ = "Autopilot is not running.";
        return;
    }
    autopilot_stop_requested_ = true;
    RefreshAutopilotSuggestions();
    status_ = busy_
        ? "Autopilot will wrap up after the current pass finishes."
        : "Autopilot wrap-up requested.";
    if (!busy_) {
        AdvanceAutopilotIfReady();
    }
}

void AegisChatApp::StartAutopilotFromCurrentContext()
{
    if (busy_) {
        status_ = "Autopilot can start after the current response finishes.";
        return;
    }

    const std::string typed_goal = Trim(std::string(message_buffer_.data()));
    if (!typed_goal.empty()) {
        SubmitMessage();
        return;
    }

    std::string goal = LatestUserPrompt(history_);
    if (Trim(goal).empty()) {
        status_ = "Enter a goal or send a project request before starting Autopilot.";
        return;
    }

    BeginAutopilotSession(goal);
    SubmitAutopilotPrompt(
        BuildAutopilotContinuationPrompt("Start the autonomous build session from the latest project goal."),
        true,
        true,
        "Autopilot is starting the build session...");
}

const CommandRun* AegisChatApp::AutopilotCurrentFailure() const
{
    if (has_verification_result_ &&
        verification_result_.has_first_failure &&
        !ValidationPassed(verification_result_.first_failure)) {
        return &verification_result_.first_failure;
    }
    if (has_response_ && ValidationFailed(last_response_)) {
        return &last_response_.validation;
    }
    if (project_scaffold_has_result_ &&
        project_scaffold_result_.has_validation &&
        !ValidationPassed(project_scaffold_result_.validation)) {
        return &project_scaffold_result_.validation;
    }
    return nullptr;
}

bool AegisChatApp::AutopilotHasValidationFailure() const
{
    return AutopilotCurrentFailure() != nullptr;
}

bool AegisChatApp::AutopilotFailureLooksDependency() const
{
    const CommandRun* failure = AutopilotCurrentFailure();
    if (failure == nullptr) {
        return false;
    }

    const std::string text = Lower(
        failure->category + "\n" +
        failure->summary + "\n" +
        failure->reason + "\n" +
        failure->stdout_text + "\n" +
        failure->stderr_text);
    return ContainsAnyTerm(text, {
        "dependency",
        "dependencies",
        "npm install",
        "pnpm install",
        "yarn install",
        "bun install",
        "node_modules",
        "cannot find module",
        "could not resolve",
        "module not found",
        "missing package",
        "missing dependency",
        "no interface 'jsx.intrinsicelements'",
        "cannot find namespace 'react'",
        "cannot find type definition file"
    });
}

bool AegisChatApp::AutopilotHasCleanValidation() const
{
    if (has_verification_result_ && Lower(verification_result_.status) == "passed") {
        return true;
    }
    if (has_response_ && last_response_.has_validation && ValidationPassed(last_response_.validation)) {
        return true;
    }
    return project_scaffold_has_result_ &&
        project_scaffold_result_.has_validation &&
        ValidationPassed(project_scaffold_result_.validation);
}

bool AegisChatApp::AutopilotRecentPassHadNoWork() const
{
    if (!has_response_) {
        return false;
    }
    if (last_response_.has_validation && !ValidationPassed(last_response_.validation)) {
        return false;
    }
    return last_response_.changes.empty() &&
        last_response_.applied.empty() &&
        last_response_.repair_attempts.empty();
}

bool AegisChatApp::AutopilotShouldContinueForQuality() const
{
    if (!has_response_) {
        return false;
    }
    return last_response_.completion_quality.should_continue;
}

std::string AegisChatApp::AutopilotQualityReason() const
{
    if (!has_response_) {
        return "";
    }
    if (!last_response_.completion_quality.reasons.empty()) {
        return last_response_.completion_quality.reasons.front();
    }
    if (!last_response_.completion_quality.next_actions.empty()) {
        return last_response_.completion_quality.next_actions.front();
    }
    if (!last_response_.completion_quality.status.empty()) {
        return "Completion quality is " + last_response_.completion_quality.status + ".";
    }
    return "";
}

void AegisChatApp::RefreshAutopilotSuggestions()
{
    autopilot_suggestions_.clear();
    if (has_workspace_autopilot_status_snapshot_) {
        const WorkspaceAutopilotStatusInfo& status = workspace_autopilot_status_;
        if (!status.phase.empty()) {
            autopilot_suggestions_.push_back("Backend phase: " + status.phase);
        }
        if (status.should_continue && !status.next_open_items.empty()) {
            autopilot_suggestions_.push_back("Next queued item: " + Shorten(status.next_open_items.front(), 80));
        }
        if (status.should_continue && !status.repair_brief.empty()) {
            autopilot_suggestions_.push_back("Repair: " + Shorten(status.repair_brief, 86));
        }
        if (status.should_continue && !status.next_action.empty()) {
            autopilot_suggestions_.push_back(Shorten(status.next_action, 90));
        } else if (!status.stop_reason.empty()) {
            autopilot_suggestions_.push_back(Shorten(status.stop_reason, 90));
        }
    }
    if (autopilot_active_) {
        autopilot_suggestions_.push_back(autopilot_stop_requested_ ? "Preparing graceful wrap-up" : "Wrap up after current pass");
        autopilot_suggestions_.push_back("Run full verify before final handoff");
    } else {
        autopilot_suggestions_.push_back("Enable Autopilot for long project work");
    }

    if (AutopilotHasValidationFailure()) {
        autopilot_suggestions_.push_back("Repair the current validation failure");
        autopilot_suggestions_.push_back("Review captured build output");
    } else if (AutopilotShouldContinueForQuality()) {
        autopilot_suggestions_.push_back("Continue completion quality pass");
        if (has_response_ && !last_response_.completion_quality.next_actions.empty()) {
            autopilot_suggestions_.push_back(Shorten(last_response_.completion_quality.next_actions.front(), 80));
        }
    } else if (AutopilotHasCleanValidation()) {
        autopilot_suggestions_.push_back("Add tests or polish the first usable slice");
        autopilot_suggestions_.push_back("Create final changelog and next steps");
    } else {
        autopilot_suggestions_.push_back("Inspect roadmap and continue next feature");
        autopilot_suggestions_.push_back("Generate validation coverage");
    }

    constexpr size_t max_suggestions = 5;
    while (autopilot_suggestions_.size() > max_suggestions) {
        autopilot_suggestions_.pop_back();
    }
}

std::string AegisChatApp::BuildAutopilotContinuationPrompt(const std::string& reason) const
{
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    std::ostringstream prompt;
    prompt << "Autopilot is enabled for this existing project and existing workspace. Continue the assigned project without waiting for another continue command.\n\n";
    prompt << "Original goal:\n" << (autopilot_goal_.empty() ? "Continue improving the selected workspace." : autopilot_goal_) << "\n\n";
    prompt << "Workspace: " << (workspace.empty() ? "[use active workspace]" : workspace) << "\n";
    prompt << "Autopilot pass: " << (autopilot_rounds_completed_ + 1) << " of " << autopilot_max_rounds_ << "\n";
    if (!reason.empty()) {
        prompt << "Reason for this pass: " << reason << "\n";
    }
    if (has_workspace_autopilot_status_snapshot_) {
        const WorkspaceAutopilotStatusInfo& status = workspace_autopilot_status_;
        prompt << "\nBackend autopilot status:\n";
        prompt << "- Phase: " << (status.phase.empty() ? "unknown" : status.phase) << "\n";
        prompt << "- Should continue: " << (status.should_continue ? "yes" : "no") << "\n";
        prompt << "- Recommended mode: " << (status.recommended_mode.empty() ? "build" : status.recommended_mode) << "\n";
        prompt << "- Pass budget: " << status.pass_budget << "\n";
        if (!status.validation_command.empty()) {
            prompt << "- Validation command: " << status.validation_command << "\n";
        }
        if (!status.latest_validation_status.empty()) {
            prompt << "- Latest validation: " << status.latest_validation_status << "\n";
        }
        if (!status.failed_step.empty()) {
            prompt << "- Failed step: " << status.failed_step << "\n";
        }
        if (!status.failed_step_command.empty()) {
            prompt << "- Failed command: " << status.failed_step_command << "\n";
        }
        if (!status.first_diagnostic.empty()) {
            prompt << "- First diagnostic: " << status.first_diagnostic << "\n";
        }
        if (!status.repair_brief.empty()) {
            prompt << "- Repair brief: " << status.repair_brief << "\n";
        }
        if (!status.next_action.empty()) {
            prompt << "- Next action: " << status.next_action << "\n";
        }
        if (!status.instruction_source.empty()) {
            prompt << "- Instruction source: " << status.instruction_source << "\n";
        }
        if (!status.instruction_files.empty()) {
            prompt << "- Instruction files: ";
            int emitted = 0;
            for (const WorkspaceInstructionStatusFileInfo& file : status.instruction_files) {
                if (file.path.empty()) {
                    continue;
                }
                if (emitted > 0) {
                    prompt << ", ";
                }
                prompt << file.path;
                ++emitted;
                if (emitted >= 6) {
                    break;
                }
            }
            prompt << "\n";
        }
        if (!status.next_open_items.empty()) {
            prompt << "\nBackend queued instruction items to work in order:\n";
            const size_t queue_count = std::min<size_t>(status.next_open_items.size(), 8);
            for (size_t i = 0; i < queue_count; ++i) {
                prompt << (i + 1) << ". " << status.next_open_items[i] << "\n";
            }
            prompt << "Use the first unfinished queue item as the primary task for this pass unless validation repair is blocking it.\n";
        }
        if (!status.suggested_prompt.empty()) {
            prompt << "- Status prompt: " << Shorten(status.suggested_prompt, 1200) << "\n";
        }
    }
    if (has_response_ && (last_response_.completion_quality.should_continue || !last_response_.completion_quality.status.empty())) {
        prompt << "\nLatest completion quality:\n";
        prompt << "- Status: " << (last_response_.completion_quality.status.empty() ? "unknown" : last_response_.completion_quality.status);
        if (last_response_.completion_quality.score > 0.0) {
            prompt << " (" << static_cast<int>(last_response_.completion_quality.score * 100.0) << "%)";
        }
        prompt << "\n";
        for (const std::string& item : last_response_.completion_quality.reasons) {
            prompt << "- Reason: " << item << "\n";
        }
        for (const std::string& item : last_response_.completion_quality.next_actions) {
            prompt << "- Next action: " << item << "\n";
        }
    }
    prompt << "\nWork loop for this pass:\n";
    prompt << "1. Read the project manifest, roadmap, recent command history, and important source files.\n";
    prompt << "2. If backend queued instruction items are present, treat them as the authoritative roadmap and complete the first unfinished item before inventing new scope.\n";
    prompt << "3. If a backend repair brief is present, fix that exact failed command and first diagnostic before adding new scope.\n";
    prompt << "4. Choose the highest-value next task: repair validation first, then complete the requested app/site/software feature slice.\n";
    prompt << "5. For app/site/software creation goals, build a complete usable version, not a placeholder: real structure, real UI/content, components, styling, responsive behavior, config, scripts, and docs as needed.\n";
    prompt << "6. Prefer larger coherent file updates over tiny one-file edits when the project is still skeletal or incomplete.\n";
    prompt << "7. If dependencies or type packages are missing, use the install/verification path before treating module-resolution errors as code defects.\n";
    prompt << "8. Run the saved validation command when available, capture errors, and use the repair loop before handing back.\n";
    prompt << "9. End with a short progress note, remaining risks, and 3 suggested next actions.\n";

    if (project_scaffold_has_result_ &&
        project_scaffold_result_.has_validation &&
        !ValidationPassed(project_scaffold_result_.validation)) {
        prompt << "\nLatest scaffold validation failure:\n";
        prompt << "Command: " << project_scaffold_result_.validation.command << "\n";
        prompt << "Summary: " << (project_scaffold_result_.validation.summary.empty()
            ? project_scaffold_result_.validation.reason
            : project_scaffold_result_.validation.summary) << "\n";
        const std::string output = Shorten(ValidationCombinedOutput(project_scaffold_result_.validation), 5000);
        if (!output.empty()) {
            prompt << "Output:\n" << output << "\n";
        }
    }

    prompt << "\nOnly declare the project at a stopping point when validation is clean or when no more useful work can be done safely in this session.";
    return prompt.str();
}

std::string AegisChatApp::BuildAutopilotFinalPrompt(const std::string& reason) const
{
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    std::ostringstream prompt;
    prompt << "Autopilot is wrapping up for this existing project and existing workspace. Do not make file changes in this response.\n\n";
    prompt << "Original goal:\n" << (autopilot_goal_.empty() ? "Continue improving the selected workspace." : autopilot_goal_) << "\n\n";
    prompt << "Workspace: " << (workspace.empty() ? "[use active workspace]" : workspace) << "\n";
    prompt << "Wrap-up reason: " << (reason.empty() ? "Autopilot reached a stopping point." : reason) << "\n";
    prompt << "Completed autopilot passes: " << autopilot_rounds_completed_ << "\n\n";
    prompt << "Final response requirements:\n";
    prompt << "1. Summarize exactly what changed and what validation/build status is known.\n";
    prompt << "2. If any build errors remain, identify the failing command and the most likely next repair.\n";
    prompt << "3. Give 3 prioritized suggestions for the next session.\n";
    prompt << "4. Keep the answer concise and useful for resuming work later.";
    return prompt.str();
}

void AegisChatApp::SubmitAutopilotPrompt(const std::string& prompt, bool apply, bool validate, const std::string& label)
{
    next_submit_apply_override_set_ = true;
    next_submit_apply_override_ = apply;
    next_submit_validation_override_set_ = true;
    next_submit_validation_override_ = validate;
    autopilot_waiting_for_result_ = true;
    status_ = label;
    SubmitMessage(prompt, false);
}

void AegisChatApp::FinishAutopilotSession(const std::string& reason)
{
    autopilot_enabled_ = false;
    autopilot_active_ = false;
    autopilot_stop_requested_ = false;
    autopilot_finishing_ = false;
    autopilot_waiting_for_result_ = false;
    autopilot_dependency_verify_attempted_ = false;
    verification_chain_repairs_remaining_ = 0;
    pending_verification_chain_repair_ = false;
    RefreshAutopilotSuggestions();
    status_ = reason.empty() ? "Autopilot stopped at a stable handoff point." : reason;
    PushToast("Autopilot finished", Shorten(status_, 110), "success");
}

void AegisChatApp::AdvanceAutopilotIfReady()
{
    if (!autopilot_active_ || busy_) {
        return;
    }

    if (autopilot_waiting_for_result_) {
        autopilot_waiting_for_result_ = false;
        ++autopilot_rounds_completed_;
        RefreshAutopilotSuggestions();
        if (autopilot_finishing_) {
            FinishAutopilotSession("Autopilot wrapped up with final thoughts.");
            return;
        }
    }

    if (autopilot_stop_requested_) {
        autopilot_finishing_ = true;
        SubmitAutopilotPrompt(
            BuildAutopilotFinalPrompt("User requested a graceful stop after the current pass."),
            false,
            false,
            "Autopilot is writing final thoughts...");
        return;
    }

    if (autopilot_rounds_completed_ >= std::max(1, autopilot_max_rounds_)) {
        autopilot_finishing_ = true;
        SubmitAutopilotPrompt(
            BuildAutopilotFinalPrompt("Reached the configured autopilot pass limit."),
            false,
            false,
            "Autopilot reached its pass limit and is wrapping up...");
        return;
    }

    if (has_workspace_autopilot_status_snapshot_) {
        const WorkspaceAutopilotStatusInfo& status = workspace_autopilot_status_;
        const std::string phase = Lower(status.phase);
        if (phase == "ready" && autopilot_rounds_completed_ >= std::max(1, autopilot_min_rounds_)) {
            autopilot_finishing_ = true;
            SubmitAutopilotPrompt(
                BuildAutopilotFinalPrompt(status.stop_reason.empty()
                    ? "Backend workspace readiness reports a clean stopping point."
                    : status.stop_reason),
                false,
                false,
                "Autopilot found a backend-confirmed stopping point...");
            return;
        }
        if (status.should_continue && !Trim(status.suggested_prompt).empty()) {
            if (!status.recommended_mode.empty()) {
                mode_ = status.recommended_mode;
            }
            max_repairs_ = std::max(max_repairs_, std::max(0, status.max_repair_attempts));
            if (!status.validation_command.empty()) {
                SetBuffer(validation_command_buffer_, status.validation_command);
                SetBuffer(validation_label_buffer_, "Workspace autopilot validation");
                SetBuffer(validation_notes_buffer_, "Loaded from backend workspace autopilot status.");
            }
            SubmitAutopilotPrompt(
                BuildAutopilotContinuationPrompt("Backend autopilot status phase " + status.phase + ": " + status.next_action),
                true,
                status.run_validation || run_validation_,
                "Autopilot is following backend workspace status...");
            return;
        }
    }

    if (AutopilotHasValidationFailure()) {
        if (!autopilot_dependency_verify_attempted_ && AutopilotFailureLooksDependency()) {
            autopilot_dependency_verify_attempted_ = true;
            verification_include_install_ = true;
            verification_continue_on_failure_ = true;
            verification_auto_repair_chain_ = true;
            verification_chain_repairs_remaining_ = std::max(verification_chain_repairs_remaining_, verification_chain_repair_limit_);
            autopilot_waiting_for_result_ = true;
            status_ = "Autopilot detected missing dependencies and is running Full Verify with install enabled...";
            VerifyWorkspace();
            return;
        }
        if ((has_verification_result_ &&
                verification_result_.has_first_failure &&
                !ValidationPassed(verification_result_.first_failure)) ||
            (has_response_ && ValidationFailed(last_response_))) {
            autopilot_waiting_for_result_ = true;
            RepairLastValidationFailure(true);
            return;
        }
        SubmitAutopilotPrompt(
            BuildAutopilotContinuationPrompt("Repair the latest scaffold validation failure."),
            true,
            true,
            "Autopilot is repairing validation...");
        return;
    }

    if (AutopilotRecentPassHadNoWork() && autopilot_rounds_completed_ >= std::max(1, autopilot_min_rounds_)) {
        autopilot_finishing_ = true;
        SubmitAutopilotPrompt(
            BuildAutopilotFinalPrompt("The last pass did not produce useful file changes or repair work."),
            false,
            false,
            "Autopilot is wrapping up after a no-change pass...");
        return;
    }

    if (AutopilotShouldContinueForQuality()) {
        SubmitAutopilotPrompt(
            BuildAutopilotContinuationPrompt("Completion quality requires another pass: " + AutopilotQualityReason()),
            true,
            true,
            "Autopilot is continuing because the project is not complete enough yet...");
        return;
    }

    if (AutopilotHasCleanValidation() && autopilot_rounds_completed_ >= std::max(1, autopilot_min_rounds_)) {
        autopilot_finishing_ = true;
        SubmitAutopilotPrompt(
            BuildAutopilotFinalPrompt("Validation is clean and the minimum autopilot pass count is complete."),
            false,
            false,
            "Autopilot found a clean stopping point...");
        return;
    }

    SubmitAutopilotPrompt(
        BuildAutopilotContinuationPrompt("Continue the next highest-value project pass."),
        true,
        true,
        "Autopilot is continuing the project...");
}

void AegisChatApp::SubmitMessage(const std::string& override_message, bool append_user_message)
{
    const std::string raw_content = Trim(override_message.empty() ? std::string(message_buffer_.data()) : override_message);
    if (raw_content.empty() && (attachments_.empty() || !append_user_message)) {
        return;
    }
    if (busy_ && append_user_message && !autopilot_active_) {
        QueueUserMessageForRetry(raw_content, attachments_, "Aegis is finishing " + (busy_label_.empty() ? std::string("the current operation") : busy_label_) + ".");
        return;
    }
    if (append_user_message && !health_.engine_ready &&
        (connection_state_ == "offline" || connection_state_ == "failed" || connection_state_ == "reconnecting")) {
        QueueUserMessageForRetry(raw_content, attachments_, "The backend is " + connection_state_ + "; retry will run automatically.");
        RefreshRuntime(true);
        return;
    }
    if (busy_ && autopilot_active_ && append_user_message) {
        const std::vector<FileContent> queued_attachments = attachments_;
        std::string display_content = raw_content.empty() ? "Use the attached workspace file(s) as context." : raw_content;
        if (!queued_attachments.empty()) {
            display_content += "\n\n" + AttachmentSummary(queued_attachments);
        }
        history_.push_back({"user", display_content, NowTimeLabel()});
        attachments_.clear();
        message_buffer_.fill('\0');
        const std::string queued_instruction = raw_content.empty() ? AttachmentSummary(queued_attachments) : raw_content;
        autopilot_goal_ = Shorten(
            Trim(autopilot_goal_) + "\n\nAdditional user instruction for the next autopilot pass:\n" + queued_instruction,
            2400);
        RefreshAutopilotSuggestions();
        SaveConversationSnapshot();
        status_ = "Queued your instruction for the next Autopilot pass.";
        PushToast("Autopilot instruction queued", Shorten(raw_content.empty() ? "Attachment context queued." : raw_content, 110), "info");
        return;
    }
    if (autopilot_enabled_ && append_user_message && !raw_content.empty()) {
        BeginAutopilotSession(raw_content);
    }

    const std::string explicit_workspace = ExtractWindowsPathFromPrompt(raw_content);
    const std::string lowered_prompt = Lower(raw_content);
    bool project_builder_intent = attachments_.empty() && ShouldRouteToProjectBuilder(raw_content);
    const bool explicit_cpp_project_creation = IsExplicitCppProjectCreationRequest(raw_content);
    if (project_builder_intent &&
        !explicit_workspace.empty() &&
        PathLooksLikeExistingProject(explicit_workspace) &&
        !explicit_cpp_project_creation &&
        !ContainsAnyTerm(lowered_prompt, {
            "from scratch", "new project", "starter project", "scaffold", "blank project", "empty folder"
        })) {
        project_builder_intent = false;
    }
    const bool immediate_build_request = PromptRequestsImmediateBuild(raw_content);
    if (project_builder_intent && immediate_build_request) {
        project_scaffold_run_install_ = true;
        project_scaffold_run_validation_ = true;
        run_validation_ = true;
    }

    std::string continuity_directive;
    const std::string known_project_target = project_scaffold_has_result_ ? project_scaffold_result_.target_path : std::string{};
    const std::string continuity_workspace = !explicit_workspace.empty()
        ? explicit_workspace
        : (!Trim(known_project_target).empty() ? known_project_target : workspace_root_);
    const bool cpp_or_console_context =
        WorkspaceLooksLikeCppProject(continuity_workspace) ||
        ContainsAnyTerm(lowered_prompt, {"c++", "cpp", "cmake", "msbuild", "sln", "visual studio", "console app", "console project"});
    const std::string inferred_validation_command = DefaultValidationCommandForWorkspace(continuity_workspace);
    const bool existing_project_followup =
        !Trim(continuity_workspace).empty() &&
        (PathLooksLikeExistingProject(continuity_workspace) || !inferred_validation_command.empty());
    if (!project_builder_intent && IsBuildOrRunFollowUp(raw_content) && existing_project_followup) {
        project_builder_intent = false;
        workspace_root_ = continuity_workspace;
        SetBuffer(workspace_buffer_, workspace_root_);
        run_validation_ = true;
        if (!inferred_validation_command.empty()) {
            next_validation_command_override_ = inferred_validation_command;
            next_validation_label_override_ = "Project build and run";
            next_validation_notes_override_ = cpp_or_console_context
                ? "Auto-selected from the existing C++ project layout for a build/run follow-up."
                : "Auto-selected from existing project files for a build/run follow-up.";
            SetBuffer(validation_command_buffer_, inferred_validation_command);
            SetBuffer(validation_label_buffer_, next_validation_label_override_);
            SetBuffer(validation_notes_buffer_, next_validation_notes_override_);
        }
        continuity_directive = BuildWorkspaceContinuityDirective(continuity_workspace, inferred_validation_command, cpp_or_console_context);
        QueueAgentActivity(
            "routing",
            cpp_or_console_context
                ? "Continuing the existing C++ project and preserving its stack."
                : "Continuing the existing project and preserving its detected stack.",
            "running",
            continuity_workspace,
            inferred_validation_command);
    }

    const bool project_builder_apply = project_builder_intent &&
        (apply_changes_ || ShouldAutoApplyPrompt(raw_content) || immediate_build_request);
    if (!explicit_workspace.empty() && !project_builder_intent) {
        workspace_root_ = explicit_workspace;
        SetBuffer(workspace_buffer_, workspace_root_);
    }

    const std::vector<FileContent> attachments = append_user_message ? attachments_ : std::vector<FileContent>{};
    std::string content = BuildMessageWithAttachments(raw_content, attachments);
    if (!continuity_directive.empty()) {
        content += "\n\n" + continuity_directive;
    }
    if (autopilot_active_ && append_user_message && !raw_content.empty()) {
        content +=
            "\n\nAutopilot full-build directive:\n"
            "- Treat this as a long-running software engineering assignment, not a one-message sketch.\n"
            "- Use the requested path/workspace exactly when one is provided.\n"
            "- Inspect the existing project before editing; if it is skeletal, build the complete usable first version in this pass.\n"
            "- Create all essential files for the requested app, website, desktop app, library, driver, or tool rather than leaving placeholders.\n"
            "- Add realistic content, structure, configs, scripts, validation commands, docs, and project memory needed to continue reliably.\n"
            "- Run validation/build when enabled, capture errors, install missing dependencies through the allowed verification path, and repair failures.\n"
            "- Keep working until there is a usable checkpoint or a concrete validation failure with captured output.";
    }
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
    route_preview_ = {};
    has_route_preview_ = false;

    AegisClient client = client_;
    const std::vector<ChatMessage> request_history = history_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    if (project_builder_intent) {
        const std::string preferred_target = explicit_workspace;
        const std::string default_builder_workspace = Trim(!config_.default_workspace.empty() ? config_.default_workspace : health_.workspace_root);
        const std::string builder_workspace = explicit_workspace.empty() && !default_builder_workspace.empty()
            ? default_builder_workspace
            : workspace;
        const bool builder_run_install = project_scaffold_run_install_;
        const bool builder_run_validation = project_scaffold_run_validation_ || run_validation_;
        const int builder_repairs = max_repairs_;
        SetBuffer(project_scaffold_prompt_buffer_, raw_content);
        status_ = project_builder_apply
            ? "Detected a project-builder request. Preparing a checkpointed workspace pass."
            : "Detected a project-builder request. Planning the safest workspace pass first.";
        history_.push_back({
            "assistant",
            project_builder_apply
                ? "Aegis is working:\n- Thinking through the project request and requested path.\n- Inspecting the target workspace before writing or validating.\n- Selecting whether this is a new scaffold, update, or existing-project build pass.\n- Preparing a file diff and checkpointed workspace plan.\n- Creating or updating project memory under `.aegis`.\n- Running validation if enabled and capturing errors for repair."
                : "Aegis is working:\n- Thinking through the project request and requested path.\n- Inspecting the target workspace before writing or validating.\n- Selecting whether this is a new scaffold, update, or existing-project build pass.\n- Preparing a file diff preview, roadmap, and project memory plan.",
            NowTimeLabel(),
            "Aegis Project Builder",
        });
        const int project_builder_progress_index = static_cast<int>(history_.size()) - 1;
        SaveConversationSnapshot();
        QueueAgentActivity("planning", "Reading project request and selecting a build route.", "running");
        QueueAgentActivity("workspace", preferred_target.empty() ? "Using configured workspace target." : "Using requested target path.", "running", preferred_target);
        StartTask(project_builder_apply ? "Running Project Builder..." : "Planning Project Builder pass...", [this, client, raw_content, builder_workspace, preferred_target, project_builder_progress_index, project_builder_apply, builder_run_install, builder_run_validation, builder_repairs]() mutable -> Completion {
            try {
                QueueAgentActivity("planning", "Fetching supported project presets.", "running");
                std::vector<ProjectScaffoldPresetInfo> presets = client.GetProjectScaffoldPresets();
                QueueAgentActivity("planning", "Generating workspace plan from prompt.", "running");
                ProjectScaffoldPlanResult plan = client.PlanProjectScaffold(raw_content, builder_workspace, preferred_target);
                const bool existing_validation = IsExistingProjectValidationMode(plan);
                QueueAgentActivity(
                    existing_validation ? "validation" : "files",
                    existing_validation
                        ? (project_builder_apply ? "Validating existing workspace without starter-file generation." : "Preparing existing-project validation preview.")
                        : (project_builder_apply ? "Writing scaffold files with checkpoint protection." : "Preparing file diff preview."),
                    "running");
                ProjectScaffoldResult result = project_builder_apply
                    ? client.ScaffoldProject(
                          plan.target_path,
                          plan.preset.id,
                          plan.project_name.empty() ? "aegis-app" : plan.project_name,
                          plan.install_command,
                          plan.validation_command,
                          plan.overwrite,
                          plan.include_gitignore,
                          raw_content,
                          builder_run_install,
                          builder_run_validation,
                          builder_repairs)
                    : client.PreviewProjectScaffold(
                          plan.target_path,
                          plan.preset.id,
                          plan.project_name.empty() ? "aegis-app" : plan.project_name,
                          plan.install_command,
                          plan.validation_command,
                          plan.overwrite,
                          plan.include_gitignore,
                          raw_content,
                          false,
                          false,
                          builder_repairs);
            return [this, presets = std::move(presets), plan = std::move(plan), result = std::move(result), project_builder_progress_index, project_builder_apply]() mutable {
                project_scaffold_presets_ = std::move(presets);
                project_scaffold_presets_loaded_ = true;
                project_scaffold_presets_requested_ = false;
                project_scaffold_plan_ = std::move(plan);
                project_scaffold_has_plan_ = true;
                project_scaffold_result_ = std::move(result);
                project_scaffold_has_result_ = true;
                project_scaffold_result_preview_ = !project_builder_apply;

                SetBuffer(project_scaffold_name_buffer_, project_scaffold_plan_.project_name.empty() ? "aegis-app" : project_scaffold_plan_.project_name);
                SetBuffer(project_scaffold_target_buffer_, project_scaffold_plan_.target_path);
                SetBuffer(project_scaffold_install_buffer_, project_scaffold_plan_.install_command);
                SetBuffer(project_scaffold_validation_buffer_, project_scaffold_plan_.validation_command);
                project_scaffold_overwrite_ = project_scaffold_plan_.overwrite;
                project_scaffold_include_gitignore_ = project_scaffold_plan_.include_gitignore;
                if (project_builder_apply) {
                    const std::string validation_command = !project_scaffold_result_.validation_command.empty()
                        ? project_scaffold_result_.validation_command
                        : project_scaffold_plan_.validation_command;
                    if (!validation_command.empty()) {
                        SetBuffer(validation_command_buffer_, validation_command);
                        SetBuffer(
                            validation_label_buffer_,
                            (project_scaffold_plan_.preset.label.empty() ? "Project Builder" : project_scaffold_plan_.preset.label) + " validation");
                        SetBuffer(validation_notes_buffer_, "Loaded from the latest Project Builder scaffold.");
                        run_validation_ = true;
                    }
                }
                if (project_builder_apply && !project_scaffold_result_.target_path.empty()) {
                    workspace_root_ = project_scaffold_result_.target_path;
                    SetBuffer(workspace_buffer_, workspace_root_);
                }
                if (project_builder_apply && !project_scaffold_result_.workspace_files.empty()) {
                    files_ = project_scaffold_result_.workspace_files;
                }

                for (const ProjectBuildStageInfo& stage : project_scaffold_result_.stages) {
                    const std::string stage_status =
                        stage.status == "succeeded" ? "success" :
                        (stage.status == "failed" ? "failed" :
                         (stage.status == "skipped" ? "warning" : "running"));
                    QueueAgentActivity(
                        stage.command.empty() ? "stage" : "command",
                        stage.label.empty() ? stage.detail : stage.label,
                        stage_status,
                        "",
                        stage.command);
                }
                if (!project_scaffold_result_.checkpoint.empty()) {
                    QueueAgentActivity("checkpoint", "Created checkpoint " + project_scaffold_result_.checkpoint + ".", "success");
                }

                for (int i = 0; i < static_cast<int>(project_scaffold_presets_.size()); ++i) {
                    if (project_scaffold_presets_[static_cast<size_t>(i)].id == project_scaffold_plan_.preset.id) {
                        selected_project_scaffold_preset_index_ = i;
                        break;
                    }
                }

                const std::string model_label = project_scaffold_plan_.preset.label.empty()
                    ? "Aegis Project Builder"
                    : ("Aegis Project Builder / " + project_scaffold_plan_.preset.label);
                const std::string chat_summary = project_builder_apply
                    ? BuildProjectScaffoldResultSummary(project_scaffold_result_)
                    : BuildProjectScaffoldChatSummary(project_scaffold_plan_, project_scaffold_result_);
                if (project_builder_progress_index >= 0 && project_builder_progress_index < static_cast<int>(history_.size())) {
                    history_[static_cast<size_t>(project_builder_progress_index)] = {
                        "assistant",
                        chat_summary,
                        NowTimeLabel(),
                        model_label,
                    };
                } else {
                    history_.push_back({"assistant", chat_summary, NowTimeLabel(), model_label});
                }
                SaveConversationSnapshot();
                pending_popup_ = "Aegis Project Builder";
                const bool existing_validation = IsExistingProjectValidationMode(project_scaffold_result_);
                if (project_builder_apply && existing_validation && project_scaffold_result_.has_validation) {
                    status_ = ValidationPassed(project_scaffold_result_.validation)
                        ? "Existing project validated in " + Shorten(project_scaffold_result_.target_path, 82) + "."
                        : "Existing project validation needs repair in " + Shorten(project_scaffold_result_.target_path, 78) + ".";
                } else if (project_builder_apply && project_scaffold_result_.has_validation) {
                    status_ = ValidationPassed(project_scaffold_result_.validation)
                        ? "Project built and validated in " + Shorten(project_scaffold_result_.target_path, 82) + "."
                        : "Project created, but validation needs repair in " + Shorten(project_scaffold_result_.target_path, 78) + ".";
                } else {
                    status_ = project_builder_apply
                        ? (existing_validation
                            ? "Existing project pass finished in " + Shorten(project_scaffold_result_.target_path, 82) + "."
                            : "Project files created in " + Shorten(project_scaffold_result_.target_path, 92) + ".")
                        : (existing_validation
                            ? "Existing-project validation preview ready. Review it in Project Builder before running validation."
                            : "Project plan and preview ready. Review it in Project Builder before creating files.");
                }
                PushToast(
                    project_builder_apply
                        ? (existing_validation
                            ? (project_scaffold_result_.has_validation && ValidationPassed(project_scaffold_result_.validation) ? "Validation passed" : "Validation captured")
                            : (project_scaffold_result_.has_validation && ValidationPassed(project_scaffold_result_.validation) ? "Project built" : "Project created"))
                        : "Project plan ready",
                    Shorten(project_scaffold_plan_.target_path, 84),
                    project_scaffold_result_.has_validation && !ValidationPassed(project_scaffold_result_.validation) ? "warning" : "success");
            };
            } catch (const std::exception& error) {
                const std::string message = error.what();
                return [this, message, project_builder_progress_index, project_builder_apply]() {
                    status_ = message;
                    const std::string summary = std::string(project_builder_apply
                        ? "Aegis Project Builder could not create the project."
                        : "Aegis Project Builder could not prepare the project plan.")
                        + "\n\n" + message
                        + "\n\nNo files were written for this request.";
                    if (project_builder_progress_index >= 0 && project_builder_progress_index < static_cast<int>(history_.size())) {
                        history_[static_cast<size_t>(project_builder_progress_index)] = {
                            "assistant",
                            summary,
                            NowTimeLabel(),
                            "Aegis Project Builder",
                        };
                    } else {
                        history_.push_back({"assistant", summary, NowTimeLabel(), "Aegis Project Builder"});
                    }
                    SaveConversationSnapshot();
                    PushToast("Project Builder failed", Shorten(message, 110), "error");
                };
            }
        });
        return;
    }

    const std::string mode = mode_;
    const bool auto_apply = ShouldAutoApplyPrompt(raw_content);
    bool apply = apply_changes_ || auto_apply;
    bool validate = run_validation_;
    if (next_submit_apply_override_set_) {
        apply = next_submit_apply_override_;
        next_submit_apply_override_set_ = false;
    }
    if (next_submit_validation_override_set_) {
        validate = next_submit_validation_override_;
        next_submit_validation_override_set_ = false;
    }
    const int repairs = max_repairs_;
    const std::string validation_command_override = next_validation_command_override_;
    const std::string validation_label_override = next_validation_label_override_;
    const std::string validation_notes_override = next_validation_notes_override_;
    next_validation_command_override_.clear();
    next_validation_label_override_.clear();
    next_validation_notes_override_.clear();
    const bool rerun_full_verify_after_repair = !validation_command_override.empty();
    cancel_response_requested_ = false;
    if (!explicit_workspace.empty()) {
        status_ = "Using requested workspace: " + Shorten(explicit_workspace, 112);
    }
    {
        std::lock_guard<std::mutex> lock(stream_delta_mutex_);
        pending_stream_deltas_.clear();
    }
    streaming_assistant_has_delta_ = false;
    streaming_preview_segment_start_ = 0;
    streaming_preview_attempt_ = 0;
    history_.push_back({"assistant", "Aegis is preparing a response...", NowTimeLabel(), "Aegis stream"});
    streaming_assistant_index_ = static_cast<int>(history_.size()) - 1;

    const std::string task_label = apply ? "Aegis is creating and applying files..." : "Aegis is thinking...";
    StartTask(task_label, [this, client, content, request_history, workspace, mode, apply, validate, repairs, auto_apply, validation_command_override, validation_label_override, validation_notes_override, rerun_full_verify_after_repair]() mutable {
        AgentResponse response = client.SendMessageStream(
            content,
            request_history,
            workspace,
            mode,
            apply,
            validate,
            repairs,
            [this](const std::string& update) {
                QueueStatusUpdate(update);
            },
            validation_command_override,
            validation_label_override,
            validation_notes_override,
            [this](const StreamDeltaInfo& delta) {
                QueueStreamDelta(delta);
            });
        WorkspaceProfileInfo workspace_profile;
        bool has_workspace_profile = false;
        std::string workspace_profile_error;
        WorkspaceAutopilotStatusInfo autopilot_status;
        bool has_autopilot_status = false;
        std::string autopilot_status_error;
        const std::string response_workspace = Trim(response.workspace_root.empty() ? workspace : response.workspace_root);
        if (!response_workspace.empty()) {
            try {
                workspace_profile = client.GetWorkspaceProfile(response_workspace);
                has_workspace_profile = true;
            } catch (const std::exception& error) {
                workspace_profile_error = error.what();
            }
            try {
                autopilot_status = client.GetWorkspaceAutopilotStatus(response_workspace);
                has_autopilot_status = true;
            } catch (const std::exception& error) {
                autopilot_status_error = error.what();
            }
        }
        return [this,
                response = std::move(response),
                auto_apply,
                rerun_full_verify_after_repair,
                validation_command_override,
                workspace_profile = std::move(workspace_profile),
                has_workspace_profile,
                workspace_profile_error = std::move(workspace_profile_error),
                autopilot_status = std::move(autopilot_status),
                has_autopilot_status,
                autopilot_status_error = std::move(autopilot_status_error)]() {
            if (cancel_response_requested_) {
                cancel_response_requested_ = false;
                if (streaming_assistant_index_ >= 0 && streaming_assistant_index_ < static_cast<int>(history_.size())) {
                    history_.erase(history_.begin() + streaming_assistant_index_);
                }
                streaming_assistant_index_ = -1;
                streaming_assistant_has_delta_ = false;
                streaming_preview_segment_start_ = 0;
                streaming_preview_attempt_ = 0;
                status_ = "Generation canceled. The last user message stayed in the transcript.";
                SaveConversationSnapshot();
                return;
            }
            last_response_ = response;
            has_response_ = true;
            selected_change_ = 0;
            selected_hunk_ = 0;
            for (const ToolEvent& event : response.events) {
                QueueAgentActivity(
                    event.kind.empty() ? "tool" : event.kind,
                    event.title.empty() ? event.detail : event.title,
                    event.status.empty() ? "running" : event.status,
                    "",
                    "");
            }
            if (response.has_task_plan) {
                QueueAgentActivity("planning", response.task_plan.objective.empty() ? "Task plan created." : response.task_plan.objective, "success");
            }
            for (const FileChange& change : response.changes) {
                QueueAgentActivity("files", (change.action.empty() ? "Update" : change.action) + ": " + change.path, "pending", change.path);
            }
            for (const std::string& applied_path : response.applied) {
                QueueAgentActivity("files", "Applied change: " + applied_path, "success", applied_path);
            }
            if (response.has_validation) {
                QueueAgentActivity(
                    "command",
                    response.validation.summary.empty() ? "Validation command finished." : response.validation.summary,
                    ValidationFailed(response) ? "failed" : "success",
                    "",
                    response.validation.command);
            }
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
            workspace_profile_ = workspace_profile;
            has_workspace_profile_snapshot_ = has_workspace_profile;
            workspace_profile_error_ = workspace_profile_error;
            workspace_autopilot_status_ = autopilot_status;
            has_workspace_autopilot_status_snapshot_ = has_autopilot_status;
            workspace_autopilot_status_error_ = autopilot_status_error;
            const std::string assistant_name = response.assistant_name.empty() ? "Aegis AI" : response.assistant_name;
            std::string model_label = response.engine;
            if (Trim(model_label).empty()) {
                model_label = models_.active_model.empty() ? config_.model_name : models_.active_model;
            }
            if (Trim(model_label).empty()) {
                model_label = config_.model_api.empty() ? "configured model" : config_.model_api;
            }
            if (streaming_assistant_index_ >= 0 && streaming_assistant_index_ < static_cast<int>(history_.size()) &&
                history_[static_cast<size_t>(streaming_assistant_index_)].role == "assistant") {
                ChatMessage& streamed = history_[static_cast<size_t>(streaming_assistant_index_)];
                streamed.content = BuildAssistantSummary(response);
                streamed.time_label = NowTimeLabel();
                streamed.model_label = model_label;
            } else {
                history_.push_back({"assistant", BuildAssistantSummary(response), NowTimeLabel(), model_label});
            }
            streaming_assistant_index_ = -1;
            streaming_assistant_has_delta_ = false;
            streaming_preview_segment_start_ = 0;
            streaming_preview_attempt_ = 0;
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
            if (rerun_full_verify_after_repair && response.has_validation && ValidationPassed(response.validation)) {
                TrackVerificationRepairActivity(
                    "Targeted command passed",
                    response.validation.summary.empty() ? "The failed command now exits cleanly." : Shorten(response.validation.summary, 180),
                    "passed",
                    response.validation.command.empty() ? validation_command_override : response.validation.command);
                pending_full_verify_after_repair_ = true;
                status_ = "Repair command passed. Rerunning Full Verify.";
                PushToast("Repair command passed", "Full Verify will rerun now.", "success");
            } else if (rerun_full_verify_after_repair && response.has_validation) {
                TrackVerificationRepairActivity(
                    "Targeted command still failing",
                    Shorten(response.validation.summary.empty() ? response.validation.reason : response.validation.summary, 180),
                    "failed",
                    response.validation.command.empty() ? validation_command_override : response.validation.command);
            } else if (rerun_full_verify_after_repair) {
                TrackVerificationRepairActivity(
                    "Targeted repair needs review",
                    "The repair turn finished without a validation result to prove the failed command.",
                    "warning",
                    validation_command_override);
            }
        };
    });
}

void AegisChatApp::PreviewComposerRoute()
{
    const std::string raw_content = Trim(std::string(message_buffer_.data()));
    if (raw_content.empty() && attachments_.empty()) {
        status_ = "Type a prompt before previewing its route.";
        return;
    }

    workspace_root_ = BufferString(workspace_buffer_.data());
    const std::string content = BuildMessageWithAttachments(raw_content, attachments_);
    AegisClient client = client_;
    const std::vector<ChatMessage> request_history = history_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string mode = mode_;

    StartTask("Previewing model route...", [this, client, content, request_history, workspace, mode]() mutable {
        AgentResponse preview = client.PreviewRoute(content, request_history, workspace, mode);
        return [this, preview = std::move(preview)]() {
            route_preview_ = preview;
            has_route_preview_ = true;

            std::string role = "route";
            if (route_preview_.has_task_plan && route_preview_.task_plan.has_routing &&
                !route_preview_.task_plan.routing.task_role.empty()) {
                role = route_preview_.task_plan.routing.task_role;
            } else if (route_preview_.has_task_plan && !route_preview_.task_plan.intent.empty()) {
                role = route_preview_.task_plan.intent;
            }

            std::string model = route_preview_.engine;
            if (!route_preview_.model_attempts.empty()) {
                const ModelAttemptInfo& primary = route_preview_.model_attempts.front();
                model = primary.model.empty() ? primary.provider_label : primary.model;
            }
            status_ = "Route preview ready: " + role + (model.empty() ? "." : (" -> " + model + "."));
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

    const bool was_autopilot = autopilot_active_;
    if (autopilot_active_) {
        autopilot_enabled_ = false;
        autopilot_active_ = false;
        autopilot_stop_requested_ = false;
        autopilot_finishing_ = false;
        autopilot_waiting_for_result_ = false;
        RefreshAutopilotSuggestions();
    }
    cancel_response_requested_ = true;
    busy_label_ = "Canceling response...";
    status_ = was_autopilot
        ? "Cancel requested. Autopilot stopped and Aegis is waiting for the current backend call to return."
        : "Cancel requested. Waiting for the current backend call to return.";
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
    const std::string feedback_task_id = last_response_.task_id;
    const std::string feedback_route = last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Applying previewed changes...", [this, client, workspace, changes, feedback_task_id, feedback_route]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, changes);
        try {
            client.RecordFeedback(
                workspace,
                "accepted",
                "Applied " + std::to_string(changes.size()) + " generated change(s).",
                "apply_all",
                feedback_task_id,
                "applied",
                "code_change",
                "",
                feedback_route);
        } catch (const std::exception&) {
        }
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
    const std::string feedback_task_id = last_response_.task_id;
    const std::string feedback_route = last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Applying selected file change...", [this, client, workspace, change, feedback_task_id, feedback_route]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, std::vector<FileChange>{change});
        try {
            client.RecordFeedback(
                workspace,
                "accepted",
                "Applied selected generated file: " + change.path,
                "apply_selected_change",
                feedback_task_id,
                "applied",
                "code_change",
                "",
                feedback_route);
        } catch (const std::exception&) {
        }
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
    const std::string feedback_task_id = last_response_.task_id;
    const std::string feedback_route = last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Applying selected diff hunk...", [this, client, workspace, hunk_change, source_path = source_change.path, hunk_number, feedback_task_id, feedback_route]() mutable {
        ApplyResult result = client.ApplyChanges(workspace, std::vector<FileChange>{hunk_change});
        try {
            client.RecordFeedback(
                workspace,
                "accepted",
                "Applied hunk " + std::to_string(hunk_number) + " from " + source_path,
                "apply_selected_hunk",
                feedback_task_id,
                "applied",
                "code_change",
                "",
                feedback_route);
        } catch (const std::exception&) {
        }
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
    const std::string feedback_task_id = last_response_.task_id;
    const std::string feedback_route = last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Restoring last file checkpoint...", [this, client, workspace, checkpoint, feedback_task_id, feedback_route]() mutable {
        RestoreResult result = client.RestoreCheckpoint(workspace, checkpoint);
        try {
            client.RecordFeedback(
                workspace,
                "rejected",
                "Rolled back checkpoint " + checkpoint + " with " + std::to_string(result.restored.size()) + " restored file item(s).",
                "rollback_last_apply",
                feedback_task_id,
                "rolled_back",
                "checkpoint",
                "",
                feedback_route);
        } catch (const std::exception&) {
        }
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
    const std::string feedback_task_id = has_response_ ? last_response_.task_id : "";
    const std::string feedback_route = has_response_ && last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Restoring selected checkpoint...", [this, client, workspace, checkpoint, feedback_task_id, feedback_route]() mutable {
        RestoreResult result = client.RestoreCheckpoint(workspace, checkpoint.id);
        try {
            client.RecordFeedback(
                workspace,
                "rejected",
                "Restored checkpoint " + checkpoint.id + " with " + std::to_string(result.restored.size()) + " restored file item(s).",
                "restore_checkpoint",
                feedback_task_id,
                "rolled_back",
                "checkpoint",
                "",
                feedback_route);
        } catch (const std::exception&) {
        }
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

void AegisChatApp::TrackVerificationRepairActivity(
    const std::string& title,
    const std::string& detail,
    const std::string& status,
    const std::string& command)
{
    VerificationRepairActivity activity;
    activity.title = title;
    activity.detail = detail;
    activity.status = status;
    activity.command = command;
    activity.created_at = NowTimeLabel();
    verification_repair_activities_.push_back(std::move(activity));
    QueueAgentActivity("repair", title + (detail.empty() ? "" : (": " + detail)), status, "", command);
    constexpr size_t max_activity_count = 18;
    while (verification_repair_activities_.size() > max_activity_count) {
        verification_repair_activities_.erase(verification_repair_activities_.begin());
    }
}

void AegisChatApp::VerifyWorkspace()
{
    AegisClient client = client_;
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    const bool include_install = verification_include_install_;
    const bool continue_on_failure = verification_continue_on_failure_;
    TrackVerificationRepairActivity(
        "Full Verify started",
        std::string(include_install ? "Install steps enabled. " : "Install steps skipped. ") +
            (continue_on_failure ? "Pipeline will continue after failures." : "Pipeline stops on first required failure."),
        "running");
    StartTask("Running full verification...", [this, client, workspace, include_install, continue_on_failure]() mutable {
        VerificationResult result = client.VerifyWorkspace(workspace, include_install, continue_on_failure, 10);
        return [this, result = std::move(result)]() {
            verification_result_ = result;
            has_verification_result_ = true;
            if (!verification_result_.workspace_root.empty()) {
                workspace_root_ = verification_result_.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            if (verification_result_.has_validation_profile) {
                validation_profile_.workspace_root = verification_result_.workspace_root;
                validation_profile_.profile = verification_result_.validation_profile;
                validation_profile_.has_profile = true;
                has_validation_profile_snapshot_ = true;
                SetBuffer(validation_command_buffer_, verification_result_.validation_profile.command);
                SetBuffer(validation_label_buffer_, verification_result_.validation_profile.label);
                SetBuffer(validation_notes_buffer_, verification_result_.validation_profile.notes);
            }
            if (verification_result_.has_first_failure) {
                if (!has_response_) {
                    last_response_ = AgentResponse{};
                    last_response_.task_id = verification_result_.task_id;
                    last_response_.workspace_root = verification_result_.workspace_root;
                    has_response_ = true;
                }
                last_response_.validation = verification_result_.first_failure;
                last_response_.has_validation = true;
                last_response_.events = verification_result_.events;
                last_response_.warnings.insert(
                    last_response_.warnings.end(),
                    verification_result_.warnings.begin(),
                    verification_result_.warnings.end());
            }
            const std::string status = verification_result_.status.empty() ? "skipped" : verification_result_.status;
            if (status == "passed") {
                status_ = "Full verification passed.";
                TrackVerificationRepairActivity("Full Verify passed", "All required verification steps completed.", "passed");
                if (verification_chain_repairs_remaining_ > 0) {
                    TrackVerificationRepairActivity(
                        "Repair chain completed",
                        "Full Verify is clean before the repair-pass limit was exhausted.",
                        "passed");
                }
                verification_chain_repairs_remaining_ = 0;
                pending_verification_chain_repair_ = false;
                PushToast("Verification passed", "All required verification steps completed.", "success");
            } else if (status == "failed") {
                const bool can_continue_chain =
                    verification_result_.has_first_failure &&
                    verification_chain_repairs_remaining_ > 0;
                status_ = can_continue_chain
                    ? ("Full verification found the next failure. Repair chain has " +
                        std::to_string(verification_chain_repairs_remaining_) + " pass(es) left.")
                    : "Full verification failed. Use Fix Validation to repair the first failure.";
                TrackVerificationRepairActivity(
                    "Full Verify failed",
                    verification_result_.has_first_failure
                        ? Shorten(verification_result_.first_failure.summary.empty() ? verification_result_.first_failure.reason : verification_result_.first_failure.summary, 180)
                        : "A required verification step failed.",
                    "failed",
                    verification_result_.has_first_failure ? verification_result_.first_failure.command : "");
                if (can_continue_chain) {
                    pending_verification_chain_repair_ = true;
                    TrackVerificationRepairActivity(
                        "Next repair queued",
                        "Aegis will target the new first failing Full Verify command.",
                        "queued",
                        verification_result_.first_failure.command);
                }
                PushToast("Verification failed", "A required verification step failed.", "error");
            } else if (status == "blocked") {
                status_ = "Full verification was blocked by command safety settings.";
                verification_chain_repairs_remaining_ = 0;
                pending_verification_chain_repair_ = false;
                TrackVerificationRepairActivity(
                    "Full Verify blocked",
                    verification_result_.has_first_failure
                        ? Shorten(verification_result_.first_failure.reason.empty() ? verification_result_.first_failure.summary : verification_result_.first_failure.reason, 180)
                        : "A verification command was blocked by safety settings.",
                    "blocked",
                    verification_result_.has_first_failure ? verification_result_.first_failure.command : "");
                PushToast("Verification blocked", "A verification command was blocked.", "warning");
            } else {
                status_ = "No verification steps were available.";
                verification_chain_repairs_remaining_ = 0;
                pending_verification_chain_repair_ = false;
                TrackVerificationRepairActivity("Full Verify skipped", "No verification steps were detected for this workspace.", "skipped");
            }
        };
    });
}

void AegisChatApp::RepairLastValidationFailure(bool continue_until_clean)
{
    if (busy_) {
        status_ = "Aegis is already working.";
        return;
    }
    if (has_verification_result_ &&
        verification_result_.has_first_failure &&
        !ValidationPassed(verification_result_.first_failure)) {
        apply_changes_ = true;
        run_validation_ = true;
        max_repairs_ = std::max(1, max_repairs_);
        const bool should_continue_chain = continue_until_clean || verification_auto_repair_chain_ || verification_chain_repairs_remaining_ > 0;
        if (should_continue_chain && verification_chain_repairs_remaining_ <= 0) {
            verification_chain_repairs_remaining_ = std::max(1, verification_chain_repair_limit_);
        }
        if (verification_chain_repairs_remaining_ > 0) {
            --verification_chain_repairs_remaining_;
        }
        next_validation_command_override_ = verification_result_.first_failure.command;
        next_validation_label_override_ = "Full Verify first failure";
        next_validation_notes_override_ = "Temporary validation override from the latest Full Verify failure.";
        status_ = should_continue_chain
            ? ("Starting Full Verify repair chain with " + std::to_string(verification_chain_repairs_remaining_) + " follow-up pass(es) remaining.")
            : "Starting Full Verify repair loop.";
        TrackVerificationRepairActivity(
            should_continue_chain ? "Repair chain step started" : "Targeted repair started",
            Shorten(verification_result_.first_failure.summary.empty()
                ? verification_result_.first_failure.reason
                : verification_result_.first_failure.summary, 180),
            "running",
            verification_result_.first_failure.command);
        SubmitMessage(BuildVerificationRepairPrompt(verification_result_), !autopilot_active_);
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
    SubmitMessage(BuildValidationRepairPrompt(last_response_), !autopilot_active_);
}

void AegisChatApp::RecordFeedback(
    const std::string& sentiment,
    const std::string& content,
    const std::string& context,
    const std::string& action,
    const std::string& target,
    const std::string& model_label,
    const std::string& task_id)
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
    const std::string resolved_task_id = !Trim(task_id).empty() ? task_id : (has_response_ ? last_response_.task_id : "");
    const std::string route_role = has_response_ && last_response_.has_task_plan && last_response_.task_plan.has_routing
        ? last_response_.task_plan.routing.task_role
        : "";
    StartTask("Recording feedback...", [this, client, workspace, sentiment, feedback_content, context, action, target, model_label, resolved_task_id, route_role]() mutable {
        client.RecordFeedback(workspace, sentiment, feedback_content, context, resolved_task_id, action, target, model_label, route_role);
        return [this, sentiment]() {
            status_ = "Feedback recorded for routing telemetry: " + sentiment + ".";
        };
    });
}

void AegisChatApp::RecordMessageFeedback(const ChatMessage& message, const std::string& sentiment)
{
    const std::string context = "message; role=" + message.role + "; time=" + message.time_label;
    const std::string action = sentiment == "copied" ? "copied" : "message_feedback";
    RecordFeedback(sentiment, message.content, context, action, "assistant_message", message.model_label);
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

void AegisChatApp::RefreshTelemetry()
{
    const std::string workspace = workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_;
    AegisClient client = client_;
    StartTask("Loading planning history...", [this, client, workspace]() mutable {
        TelemetrySnapshot snapshot = client.GetTelemetry(workspace, 20);
        RouteQualitySnapshot route_quality;
        bool route_quality_loaded = false;
        std::string route_quality_error;
        std::vector<RouteHealthInfo> route_health;
        bool route_health_loaded = false;
        std::string route_health_error;
        FallbackInspectorSnapshot fallback_inspector;
        bool fallback_inspector_loaded = false;
        std::string fallback_inspector_error;
        RoutePolicyDiffInfo route_policy_diff;
        bool route_policy_diff_loaded = false;
        std::string route_policy_diff_error;
        try {
            route_quality = client.GetRouteQuality(workspace, 200);
            route_quality_loaded = true;
        } catch (const std::exception& error) {
            route_quality_error = error.what();
        }
        try {
            route_health = client.GetRouteHealth(workspace, 200);
            route_health_loaded = true;
        } catch (const std::exception& error) {
            route_health_error = error.what();
        }
        try {
            fallback_inspector = client.GetFallbackInspector(workspace, 20);
            fallback_inspector_loaded = true;
        } catch (const std::exception& error) {
            fallback_inspector_error = error.what();
        }
        try {
            route_policy_diff = client.GetRoutePolicyDiff(workspace, 200, 1);
            route_policy_diff_loaded = true;
        } catch (const std::exception& error) {
            route_policy_diff_error = error.what();
        }

        return [this,
                snapshot = std::move(snapshot),
                route_quality = std::move(route_quality),
                route_quality_loaded,
                route_quality_error = std::move(route_quality_error),
                route_health = std::move(route_health),
                route_health_loaded,
                route_health_error = std::move(route_health_error),
                fallback_inspector = std::move(fallback_inspector),
                fallback_inspector_loaded,
                fallback_inspector_error = std::move(fallback_inspector_error),
                route_policy_diff = std::move(route_policy_diff),
                route_policy_diff_loaded,
                route_policy_diff_error = std::move(route_policy_diff_error)]() mutable {
            telemetry_ = std::move(snapshot);
            telemetry_loaded_ = true;
            route_quality_ = std::move(route_quality);
            route_quality_loaded_ = route_quality_loaded;
            route_quality_error_ = std::move(route_quality_error);
            route_health_ = std::move(route_health);
            route_health_loaded_ = route_health_loaded;
            route_health_error_ = std::move(route_health_error);
            fallback_inspector_ = std::move(fallback_inspector);
            fallback_inspector_loaded_ = fallback_inspector_loaded;
            fallback_inspector_error_ = std::move(fallback_inspector_error);
            route_policy_diff_ = std::move(route_policy_diff);
            route_policy_diff_loaded_ = route_policy_diff_loaded;
            route_policy_diff_error_ = std::move(route_policy_diff_error);
            if (fallback_inspector_.tasks.empty()) {
                selected_fallback_inspector_task_index_ = -1;
            } else {
                selected_fallback_inspector_task_index_ = std::clamp(
                    selected_fallback_inspector_task_index_ < 0 ? 0 : selected_fallback_inspector_task_index_,
                    0,
                    static_cast<int>(fallback_inspector_.tasks.size()) - 1);
            }
            if (!telemetry_.workspace_root.empty()) {
                workspace_root_ = telemetry_.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            } else if (!route_quality_.workspace_root.empty()) {
                workspace_root_ = route_quality_.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            } else if (!fallback_inspector_.workspace_root.empty()) {
                workspace_root_ = fallback_inspector_.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            status_ = "Loaded " + std::to_string(telemetry_.context_budgets.size()) +
                " planning budget(s) and " + std::to_string(telemetry_.model_attempts.size()) + " model attempt(s).";
            if (route_quality_loaded_) {
                status_ += " Route quality score: " + FormatNumber(route_quality_.overview.reliability_score, true, 1) + ".";
            } else if (!route_quality_error_.empty()) {
                status_ += " Route-quality rollup unavailable.";
            }
            if (route_health_loaded_) {
                status_ += " Route health: " + std::to_string(route_health_.size()) + " signal(s).";
            } else if (!route_health_error_.empty()) {
                status_ += " Route health unavailable.";
            }
            if (route_policy_diff_loaded_) {
                status_ += " Policy diff: " + std::to_string(route_policy_diff_.role_proposals.size()) + " role proposal(s).";
            } else if (!route_policy_diff_error_.empty()) {
                status_ += " Policy diff unavailable.";
            }
            if (fallback_inspector_loaded_) {
                status_ += " Fallback inspector: " + std::to_string(fallback_inspector_.tasks.size()) + " task(s).";
            } else if (!fallback_inspector_error_.empty()) {
                status_ += " Fallback inspector unavailable.";
            }
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

void AegisChatApp::RefreshWorkspaceProfile()
{
    AegisClient client = client_;
    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    StartTask("Loading workspace profile...", [this, client, workspace]() mutable {
        WorkspaceProfileInfo profile = client.GetWorkspaceProfile(workspace);
        WorkspaceAutopilotStatusInfo autopilot_status;
        std::string autopilot_error;
        bool has_autopilot_status = false;
        try {
            autopilot_status = client.GetWorkspaceAutopilotStatus(profile.workspace_root.empty() ? workspace : profile.workspace_root);
            has_autopilot_status = true;
        } catch (const std::exception& error) {
            autopilot_error = error.what();
        }
        return [this,
                profile = std::move(profile),
                autopilot_status = std::move(autopilot_status),
                has_autopilot_status,
                autopilot_error = std::move(autopilot_error)]() {
            workspace_profile_ = profile;
            has_workspace_profile_snapshot_ = true;
            workspace_profile_error_.clear();
            workspace_autopilot_status_ = autopilot_status;
            has_workspace_autopilot_status_snapshot_ = has_autopilot_status;
            workspace_autopilot_status_error_ = autopilot_error;
            if (!profile.workspace_root.empty()) {
                workspace_root_ = profile.workspace_root;
                SetBuffer(workspace_buffer_, workspace_root_);
            }
            if (profile.has_manifest && !profile.manifest.validation_command.empty()) {
                SetBuffer(validation_command_buffer_, profile.manifest.validation_command);
                if (!profile.manifest.preset_label.empty()) {
                    SetBuffer(validation_label_buffer_, profile.manifest.preset_label + " validation");
                }
                SetBuffer(validation_notes_buffer_, "Loaded from .aegis/project.json.");
            }
            status_ = profile.has_manifest
                ? "Loaded workspace profile: " + (profile.manifest.title.empty() ? profile.manifest.project_name : profile.manifest.title)
                : "No Aegis project manifest found for this workspace.";
            if (has_autopilot_status && !autopilot_status.phase.empty()) {
                RefreshAutopilotSuggestions();
            }
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

void AegisChatApp::HydrateProjectBuilderDefaults()
{
    if (BufferString(project_scaffold_name_buffer_.data()).empty()) {
        SetBuffer(project_scaffold_name_buffer_, "aegis-app");
    }

    if (BufferString(project_scaffold_target_buffer_.data()).empty()) {
        std::string active_workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
        if (active_workspace.empty()) {
            active_workspace = "workspace";
        }
        const std::filesystem::path default_target =
            std::filesystem::path(Utf8ToWide(active_workspace)) / L"NewAegisProject";
        SetBuffer(project_scaffold_target_buffer_, WideToUtf8(default_target.wstring()));
    }

    if (!project_scaffold_presets_.empty()) {
        selected_project_scaffold_preset_index_ = std::clamp(
            selected_project_scaffold_preset_index_,
            0,
            static_cast<int>(project_scaffold_presets_.size()) - 1);
        const ProjectScaffoldPresetInfo& preset =
            project_scaffold_presets_[static_cast<size_t>(selected_project_scaffold_preset_index_)];
        if (BufferString(project_scaffold_install_buffer_.data()).empty()) {
            SetBuffer(project_scaffold_install_buffer_, preset.install_command);
        }
        if (BufferString(project_scaffold_validation_buffer_.data()).empty()) {
            SetBuffer(project_scaffold_validation_buffer_, preset.validation_command);
        }
    }
}

void AegisChatApp::RefreshProjectBuilderPresets()
{
    AegisClient client = client_;
    project_scaffold_presets_requested_ = true;
    StartTask("Loading project builder presets...", [this, client]() mutable {
        std::vector<ProjectScaffoldPresetInfo> presets = client.GetProjectScaffoldPresets();
        return [this, presets = std::move(presets)]() {
            project_scaffold_presets_ = presets;
            project_scaffold_presets_loaded_ = true;
            project_scaffold_presets_requested_ = false;
            if (project_scaffold_presets_.empty()) {
                selected_project_scaffold_preset_index_ = 0;
                status_ = "No project builder presets returned by the backend.";
                return;
            }
            selected_project_scaffold_preset_index_ = std::clamp(
                selected_project_scaffold_preset_index_,
                0,
                static_cast<int>(project_scaffold_presets_.size()) - 1);
            HydrateProjectBuilderDefaults();
            status_ = "Loaded " + std::to_string(project_scaffold_presets_.size()) + " project builder presets.";
        };
    });
}

void AegisChatApp::PlanProjectFromPrompt()
{
    std::string prompt = BufferString(project_scaffold_prompt_buffer_.data());
    if (prompt.empty()) {
        prompt = BufferString(message_buffer_.data());
    }
    if (prompt.empty()) {
        status_ = "Enter a project prompt before planning.";
        PushToast("Project builder", status_, "warning");
        return;
    }

    const std::string workspace = Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_);
    const std::string preferred_target = BufferString(project_scaffold_target_buffer_.data());
    AegisClient client = client_;
    StartTask("Planning project from prompt...", [this, client, prompt, workspace, preferred_target]() mutable {
        ProjectScaffoldPlanResult plan = client.PlanProjectScaffold(prompt, workspace, preferred_target);
        ProjectScaffoldResult preview = client.PreviewProjectScaffold(
            plan.target_path,
            plan.preset.id,
            plan.project_name.empty() ? "aegis-app" : plan.project_name,
            plan.install_command,
            plan.validation_command,
            plan.overwrite,
            plan.include_gitignore,
            prompt,
            false,
            false,
            max_repairs_);
        return [this, plan = std::move(plan), preview = std::move(preview)]() mutable {
            project_scaffold_plan_ = std::move(plan);
            project_scaffold_has_plan_ = true;
            project_scaffold_result_ = std::move(preview);
            project_scaffold_has_result_ = true;
            project_scaffold_result_preview_ = true;

            SetBuffer(project_scaffold_name_buffer_, project_scaffold_plan_.project_name.empty() ? "aegis-app" : project_scaffold_plan_.project_name);
            SetBuffer(project_scaffold_target_buffer_, project_scaffold_plan_.target_path);
            SetBuffer(project_scaffold_install_buffer_, project_scaffold_plan_.install_command);
            SetBuffer(project_scaffold_validation_buffer_, project_scaffold_plan_.validation_command);
            project_scaffold_overwrite_ = project_scaffold_plan_.overwrite;
            project_scaffold_include_gitignore_ = project_scaffold_plan_.include_gitignore;

            for (int i = 0; i < static_cast<int>(project_scaffold_presets_.size()); ++i) {
                if (project_scaffold_presets_[static_cast<size_t>(i)].id == project_scaffold_plan_.preset.id) {
                    selected_project_scaffold_preset_index_ = i;
                    break;
                }
            }

            status_ = project_scaffold_plan_.message.empty() ? "Project plan and preview ready." : project_scaffold_plan_.message;
            PushToast("Project plan ready", Shorten(project_scaffold_plan_.preset.label + " -> " + project_scaffold_plan_.project_name, 84), "success");
        };
    });
}

void AegisChatApp::PreviewProjectFromBuilder()
{
    if (project_scaffold_presets_.empty()) {
        status_ = "Load project builder presets before previewing a project.";
        RefreshProjectBuilderPresets();
        return;
    }

    selected_project_scaffold_preset_index_ = std::clamp(
        selected_project_scaffold_preset_index_,
        0,
        static_cast<int>(project_scaffold_presets_.size()) - 1);
    const ProjectScaffoldPresetInfo preset =
        project_scaffold_presets_[static_cast<size_t>(selected_project_scaffold_preset_index_)];
    const std::string target = BufferString(project_scaffold_target_buffer_.data());
    const std::string project_name = BufferString(project_scaffold_name_buffer_.data());
    const std::string prompt = BufferString(project_scaffold_prompt_buffer_.data());
    const std::string install_command = BufferString(project_scaffold_install_buffer_.data());
    const std::string validation_command = BufferString(project_scaffold_validation_buffer_.data());
    const bool overwrite = project_scaffold_overwrite_;
    const bool include_gitignore = project_scaffold_include_gitignore_;
    const bool planned_existing_validation =
        project_scaffold_has_plan_ && IsExistingProjectValidationMode(project_scaffold_plan_);

    if (target.empty()) {
        status_ = "Choose a target folder before previewing.";
        PushToast("Project builder", status_, "warning");
        return;
    }

    AegisClient client = client_;
    StartTask(planned_existing_validation ? "Previewing existing-project validation..." : "Previewing project scaffold...", [this,
                                                                                                                              client,
                                                                                                                              target,
                                                                                                                              preset,
                                                                                                                              project_name,
                                                                                                                              prompt,
                                                                                                                              install_command,
                                                                                                                              validation_command,
                                                                                                                              overwrite,
                                                                                                                              include_gitignore]() mutable {
        ProjectScaffoldResult result = client.PreviewProjectScaffold(
            target,
            preset.id,
            project_name.empty() ? "aegis-app" : project_name,
            install_command,
            validation_command,
            overwrite,
            include_gitignore,
            prompt,
            false,
            false,
            max_repairs_);
        return [this, result = std::move(result)]() {
            project_scaffold_result_ = result;
            project_scaffold_has_result_ = true;
            project_scaffold_result_preview_ = true;
            const bool existing_validation = IsExistingProjectValidationMode(result);
            status_ = result.message.empty()
                ? (existing_validation ? "Existing-project validation preview ready." : "Project scaffold preview ready.")
                : result.message;
            PushToast(existing_validation ? "Validation preview ready" : "Project preview ready", Shorten(result.target_path, 84), "info");
        };
    });
}

void AegisChatApp::ScaffoldProjectFromBuilder()
{
    if (project_scaffold_presets_.empty()) {
        status_ = "Load project builder presets before creating a project.";
        RefreshProjectBuilderPresets();
        return;
    }

    selected_project_scaffold_preset_index_ = std::clamp(
        selected_project_scaffold_preset_index_,
        0,
        static_cast<int>(project_scaffold_presets_.size()) - 1);
    const ProjectScaffoldPresetInfo preset =
        project_scaffold_presets_[static_cast<size_t>(selected_project_scaffold_preset_index_)];
    const std::string target = BufferString(project_scaffold_target_buffer_.data());
    const std::string project_name = BufferString(project_scaffold_name_buffer_.data());
    const std::string prompt = BufferString(project_scaffold_prompt_buffer_.data());
    const std::string install_command = BufferString(project_scaffold_install_buffer_.data());
    const std::string validation_command = BufferString(project_scaffold_validation_buffer_.data());
    const bool overwrite = project_scaffold_overwrite_;
    const bool include_gitignore = project_scaffold_include_gitignore_;
    const bool run_install = project_scaffold_run_install_;
    const bool run_validation = project_scaffold_run_validation_;
    const int repairs = max_repairs_;
    const bool planned_existing_validation =
        project_scaffold_has_plan_ && IsExistingProjectValidationMode(project_scaffold_plan_);

    if (target.empty()) {
        status_ = planned_existing_validation
            ? "Choose the existing project folder to validate."
            : "Choose a target folder for the new project.";
        PushToast("Project builder", status_, "warning");
        return;
    }

    AegisClient client = client_;
    std::ostringstream working_note;
    working_note << "Aegis is working:\n";
    if (planned_existing_validation) {
        working_note << "- Inspecting the existing workspace and saved project memory.\n";
        working_note << "- Preparing a validation/build pass without starter-file generation.\n";
        working_note << "- Reusing the validation profile and capturing output for the repair loop.\n";
    } else {
        working_note << "- Inspecting the target workspace and existing generated files.\n";
        working_note << "- Preparing a plan, diff preview, and checkpointed write.\n";
        working_note << "- Creating project memory under `.aegis` for roadmap, decisions, file index, commands, and known errors.\n";
    }
    if (run_install && !install_command.empty()) {
        working_note << "- Running install command: `" << install_command << "`.\n";
    }
    if (run_validation && !validation_command.empty()) {
        working_note << "- Running validation/build command: `" << validation_command << "`.\n";
        working_note << "- Capturing stdout/stderr so repairs can start from real errors.\n";
    } else if (!validation_command.empty()) {
        working_note << "- Saving validation command for the next repair/build pass.\n";
    }
    history_.push_back({"assistant", working_note.str(), NowTimeLabel(), "Aegis Project Builder"});
    const int project_builder_create_index = static_cast<int>(history_.size()) - 1;
    SaveConversationSnapshot();
    StartTask(planned_existing_validation ? "Validating existing project..." : "Creating project scaffold...", [this,
                                                                                                                client,
                                                                                                                target,
                                                                                                                preset,
                                                                                                                project_name,
                                                                                                                prompt,
                                                                                                                install_command,
                                                                                                                validation_command,
                                                                                                                overwrite,
                                                                                                                include_gitignore,
                                                                                                                run_install,
                                                                                                                run_validation,
                                                                                                                repairs,
                                                                                                                project_builder_create_index,
                                                                                                                planned_existing_validation]() mutable -> Completion {
        try {
            ProjectScaffoldResult result = client.ScaffoldProject(
                target,
                preset.id,
                project_name.empty() ? "aegis-app" : project_name,
                install_command,
                validation_command,
                overwrite,
                include_gitignore,
                prompt,
                run_install,
                run_validation,
                repairs);
        return [this, result = std::move(result), project_builder_create_index]() {
            project_scaffold_result_ = result;
            project_scaffold_has_result_ = true;
            project_scaffold_result_preview_ = false;
            const bool existing_validation = IsExistingProjectValidationMode(result);
            if (existing_validation && result.has_validation) {
                status_ = ValidationPassed(result.validation)
                    ? "Existing project validated in " + Shorten(result.target_path, 82) + "."
                    : "Existing project validation needs repair in " + Shorten(result.target_path, 78) + ".";
            } else if (result.has_validation) {
                status_ = ValidationPassed(result.validation)
                    ? "Project built and validated in " + Shorten(result.target_path, 82) + "."
                    : "Project created, but validation needs repair in " + Shorten(result.target_path, 78) + ".";
            } else {
                status_ = result.message.empty()
                    ? (existing_validation ? "Existing project pass finished." : "Project scaffold created.")
                    : result.message;
            }
            PushToast(
                existing_validation
                    ? (result.has_validation && ValidationPassed(result.validation) ? "Validation passed" : "Validation captured")
                    : (result.has_validation && ValidationPassed(result.validation) ? "Project built" : "Project created"),
                Shorten(result.target_path, 84),
                result.has_validation && !ValidationPassed(result.validation) ? "warning" : "success");
            if (!result.validation_command.empty()) {
                SetBuffer(validation_command_buffer_, result.validation_command);
                SetBuffer(validation_label_buffer_, result.preset.label + " validation");
                SetBuffer(validation_notes_buffer_, "Generated by Aegis Project Builder.");
            }
            const std::string model_label = existing_validation
                ? "Aegis Project Builder / Validate Existing"
                : (result.preset.label.empty()
                    ? "Aegis Project Builder"
                    : ("Aegis Project Builder / " + result.preset.label));
            if (project_builder_create_index >= 0 && project_builder_create_index < static_cast<int>(history_.size())) {
                history_[static_cast<size_t>(project_builder_create_index)] = {
                    "assistant",
                    BuildProjectScaffoldResultSummary(result),
                    NowTimeLabel(),
                    model_label,
                };
            } else {
                history_.push_back({"assistant", BuildProjectScaffoldResultSummary(result), NowTimeLabel(), model_label});
            }
            SaveConversationSnapshot();
        };
        } catch (const std::exception& error) {
            const std::string message = error.what();
            return [this, message, project_builder_create_index, planned_existing_validation]() {
                status_ = message;
                const std::string summary = std::string(planned_existing_validation
                    ? "Aegis Project Builder could not validate the existing project.\n\n"
                    : "Aegis Project Builder could not create the project.\n\n")
                    + message
                    + "\n\nNo files were written for this request.";
                if (project_builder_create_index >= 0 && project_builder_create_index < static_cast<int>(history_.size())) {
                    history_[static_cast<size_t>(project_builder_create_index)] = {
                        "assistant",
                        summary,
                        NowTimeLabel(),
                        "Aegis Project Builder",
                    };
                } else {
                    history_.push_back({"assistant", summary, NowTimeLabel(), "Aegis Project Builder"});
                }
                SaveConversationSnapshot();
                PushToast("Project Builder failed", Shorten(message, 110), "error");
            };
        }
    });
}

void AegisChatApp::UseScaffoldedProjectAsWorkspace()
{
    if (!project_scaffold_has_result_ || Trim(project_scaffold_result_.target_path).empty()) {
        status_ = "Create a project before switching workspaces.";
        return;
    }

    workspace_root_ = project_scaffold_result_.target_path;
    SetBuffer(workspace_buffer_, workspace_root_);
    files_ = project_scaffold_result_.workspace_files;
    checkpoints_ = {};
    selected_file_index_ = -1;
    has_selected_file_ = false;
    has_validation_profile_snapshot_ = false;
    has_workspace_profile_snapshot_ = false;
    has_workspace_autopilot_status_snapshot_ = false;
    workspace_profile_error_.clear();
    workspace_autopilot_status_error_.clear();
    if (!project_scaffold_result_.validation_command.empty()) {
        SetBuffer(validation_command_buffer_, project_scaffold_result_.validation_command);
        SetBuffer(validation_label_buffer_, project_scaffold_result_.preset.label + " validation");
        SetBuffer(validation_notes_buffer_, "Generated by Aegis Project Builder.");
    }
    status_ = "Workspace switched to scaffolded project.";
    PushToast("Workspace selected", Shorten(workspace_root_, 84), "success");
    RefreshWorkspaceProfile();
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
    model_manager_ = snapshot.model_manager;
    model_benchmarks_ = snapshot.model_benchmarks;
    route_apply_preview_ = snapshot.route_apply_preview;
    route_apply_preview_loaded_ = snapshot.has_route_apply_preview;
    route_apply_preview_error_ = snapshot.route_apply_preview_error;
    model_registry_audit_ = snapshot.model_registry_audit;
    model_registry_audit_loaded_ = snapshot.has_model_registry_audit;
    model_registry_audit_error_ = snapshot.model_registry_audit_error;
    model_registry_checkpoints_ = snapshot.model_registry_checkpoints;
    model_registry_checkpoints_loaded_ = snapshot.has_model_registry_checkpoints;
    model_registry_checkpoints_error_ = snapshot.model_registry_checkpoints_error;
    workspace_profile_ = snapshot.workspace_profile;
    has_workspace_profile_snapshot_ = snapshot.has_workspace_profile;
    workspace_profile_error_ = snapshot.workspace_profile_error;
    workspace_autopilot_status_ = snapshot.workspace_autopilot_status;
    has_workspace_autopilot_status_snapshot_ = snapshot.has_workspace_autopilot_status;
    workspace_autopilot_status_error_ = snapshot.workspace_autopilot_status_error;
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
    draw->AddRectFilled(badge_pos, ImVec2(badge_pos.x + 45.0f, badge_pos.y + 20.0f), Color(92, 21, 30, 0.92f), 10.0f);
    draw->AddRect(badge_pos, ImVec2(badge_pos.x + 45.0f, badge_pos.y + 20.0f), Color(255, 120, 132, 0.22f + Pulse(2.4f) * 0.18f), 10.0f);
    DrawBitmapIcon(draw, IconGlyph::Bolt, ImVec2(badge_pos.x + 7.0f, badge_pos.y + 5.0f), 10.0f, Color(255, 120, 132));
    draw->AddText(ImVec2(badge_pos.x + 20.0f, badge_pos.y + 3.0f), Color(255, 120, 132), "Pro");
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
    const bool online = connection_state_ == "connected" && health_.engine_ready && health_.model_ready;
    const bool reconnecting = connection_state_ == "reconnecting";
    const ImU32 state_color = online ? Color(38, 221, 123) : (reconnecting ? Color(234, 179, 85) : Color(239, 68, 68));
    const ImU32 state_ring = online ? Color(38, 221, 123, 0.14f) : (reconnecting ? Color(234, 179, 85, 0.16f) : Color(239, 68, 68, 0.14f));
    const char* state_label = online ? "Connected" : (reconnecting ? "Reconnecting" : (connection_state_ == "failed" ? "Failed" : "Offline"));
    draw->AddCircleFilled(ImVec2(online_pos.x + 8.0f, online_pos.y + 18.0f), online || reconnecting ? 7.0f + Pulse(2.8f) * 2.0f : 5.0f, state_ring);
    draw->AddCircleFilled(ImVec2(online_pos.x + 8.0f, online_pos.y + 18.0f), 4.0f, state_color);
    draw->AddText(ImVec2(online_pos.x + 20.0f, online_pos.y + 10.0f), state_color, state_label);
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
    draw->AddRectFilled(logo_pos, ImVec2(logo_pos.x + 44.0f, logo_pos.y + 44.0f), Color(26, 9, 12), 13.0f);
    DrawBitmapIcon(draw, IconGlyph::Shield, ImVec2(logo_pos.x + 7.0f, logo_pos.y + 7.0f), 30.0f, Color(248, 64, 82));
    ImGui::SetCursorPos(ImVec2(70.0f, 20.0f));
    TextColor("Aegis AI", Rgba(246, 248, 251));
    ImGui::SetCursorPos(ImVec2(70.0f, 43.0f));
    TextMuted("Your AI Assistant");

    ImGui::SetCursorPosY(94.0f);
    if (IconTextButton("new_chat", IconGlyph::Plus, "New Chat", ImVec2(-1.0f, 42.0f), Rgba(210, 39, 55), Rgba(239, 68, 68), Rgba(255, 255, 255))) {
        StartNewChat();
        active_nav_ = "chat";
    }
    ImGui::Separator();
    ImGui::Dummy(ImVec2(0.0f, 6.0f));

    if (NavButton("nav_chat", IconGlyph::Chat, "Chat", active_nav_ == "chat")) {
        active_nav_ = "chat";
        mode_ = "chat";
        status_ = "Chat workspace active.";
    }
    if (NavButton("nav_projects", IconGlyph::Explore, "Projects", active_nav_ == "projects")) {
        active_nav_ = "projects";
        pending_popup_ = "Aegis Project Builder";
        status_ = "Opened project builder.";
    }
    if (NavButton("nav_agent", IconGlyph::Agents, "Code Agent", active_nav_ == "agent")) {
        active_nav_ = "agent";
        mode_ = "develop";
        status_ = "Code Agent route active.";
    }
    if (NavButton("nav_build", IconGlyph::Code, "Build/Repair", active_nav_ == "build")) {
        active_nav_ = "build";
        mode_ = "build";
        run_validation_ = true;
        pending_popup_ = "Aegis Build Queue";
        status_ = "Build and repair workspace active.";
    }
    if (NavButton("nav_models", IconGlyph::Globe, "Models", active_nav_ == "models")) {
        active_nav_ = "models";
        pending_popup_ = "Aegis Model Stack";
        status_ = "Opened model stack.";
    }
    if (NavButton("nav_settings", IconGlyph::Sliders, "Settings", active_nav_ == "settings")) {
        active_nav_ = "settings";
        pending_popup_ = "Aegis Settings";
        status_ = "Opened settings.";
    }
    if (NavButton("nav_history", IconGlyph::History, "History", active_nav_ == "history")) {
        active_nav_ = "history";
        RefreshConversationLibrary();
        pending_popup_ = "Aegis Conversations";
        status_ = "Opened conversations.";
    }
    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    ImGui::TextUnformatted("Recent Chats");
    ImGui::SameLine(ImGui::GetContentRegionAvail().x + ImGui::GetCursorPosX() - 24.0f);
    DrawBitmapIcon(draw, IconGlyph::Search, ImGui::GetCursorScreenPos(), 14.0f, Color(151, 160, 171));
    ImGui::Dummy(ImVec2(16.0f, 16.0f));
    ImGui::Dummy(ImVec2(0.0f, 4.0f));

    int recent_index = 0;
    if (!current_conversation_id_.empty() && !current_conversation_archived_) {
        const std::string label = Shorten(current_conversation_title_.empty() ? ConversationTitleFromHistory(history_) : current_conversation_title_, 30);
        const std::string preview = ConversationPreviewFromHistory(history_);
        const ImVec2 row_pos = ImGui::GetCursorScreenPos();
        const ImVec2 row_size(ImGui::GetContentRegionAvail().x, 34.0f);
        ImGui::InvisibleButton("recent_current", row_size);
        if (ImGui::IsItemClicked()) {
            active_nav_ = "chat";
            status_ = "Current conversation is already open.";
        }
        draw->AddRectFilled(row_pos, ImVec2(row_pos.x + row_size.x, row_pos.y + row_size.y), Color(68, 24, 31, 0.78f), 7.0f);
        draw->AddRectFilled(ImVec2(row_pos.x, row_pos.y + 6.0f), ImVec2(row_pos.x + 3.0f, row_pos.y + row_size.y - 6.0f), Color(248, 64, 82), 2.0f);
        DrawBitmapIcon(draw, current_conversation_pinned_ ? IconGlyph::Shield : IconGlyph::Chat, ImVec2(row_pos.x + 13.0f, row_pos.y + 10.0f), 13.0f, Color(248, 64, 82));
        draw->AddText(ImVec2(row_pos.x + 34.0f, row_pos.y + 8.0f), Color(255, 120, 132), label.empty() ? "Current chat" : label.c_str());
        draw->AddText(ImVec2(row_pos.x + row_size.x - 48.0f, row_pos.y + 8.0f), Color(126, 136, 149), Shorten(preview.empty() ? "now" : preview, 6).c_str());
        ++recent_index;
    }
    for (int i = 0; i < static_cast<int>(conversations_.size()); ++i) {
        const LocalConversationSummary& conversation = conversations_[static_cast<size_t>(i)];
        if (recent_index >= 7) {
            break;
        }
        if (conversation.archived) {
            continue;
        }
        if (!current_conversation_id_.empty() && conversation.id == current_conversation_id_) {
            continue;
        }
        const std::string label = Shorten(conversation.title.empty() ? "Untitled chat" : conversation.title, 30);
        const std::string time = conversation.saved_at;
        const bool active = conversation.id == current_conversation_id_;
        const ImVec2 row_pos = ImGui::GetCursorScreenPos();
        const ImVec2 row_size(ImGui::GetContentRegionAvail().x, 34.0f);
        ImGui::InvisibleButton(("recent_" + std::to_string(recent_index)).c_str(), row_size);
        if (ImGui::IsItemClicked()) {
            LoadConversationFromLibrary(i);
        }
        draw->AddRectFilled(row_pos, ImVec2(row_pos.x + row_size.x, row_pos.y + row_size.y), active ? Color(68, 24, 31, 0.78f) : Color(0, 0, 0, 0), 7.0f);
        if (active) {
            draw->AddRectFilled(ImVec2(row_pos.x, row_pos.y + 6.0f), ImVec2(row_pos.x + 3.0f, row_pos.y + row_size.y - 6.0f), Color(248, 64, 82), 2.0f);
        }
        DrawBitmapIcon(draw, conversation.pinned ? IconGlyph::Shield : IconGlyph::Chat, ImVec2(row_pos.x + 13.0f, row_pos.y + 10.0f), 13.0f, active ? Color(248, 64, 82) : Color(154, 164, 176));
        draw->AddText(ImVec2(row_pos.x + 34.0f, row_pos.y + 8.0f), active ? Color(255, 120, 132) : Color(209, 216, 224), label.c_str());
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
            DrawBitmapIcon(draw, i == 0 ? IconGlyph::Chat : IconGlyph::Mail, ImVec2(row_pos.x + 13.0f, row_pos.y + 10.0f), 13.0f, i == 0 ? Color(248, 64, 82) : Color(154, 164, 176));
            draw->AddText(ImVec2(row_pos.x + 34.0f, row_pos.y + 8.0f), i == 0 ? Color(255, 120, 132) : Color(209, 216, 224), samples[i]);
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
        draw->AddCircleFilled(ImVec2(avatar.x + 24.0f, avatar.y + 25.0f), 19.0f, Color(239, 68, 68));
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

void AegisChatApp::RenderConversationSidebar()
{
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(7, 9, 13, 0.96f));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(52, 55, 64, 0.70f));
    ImGui::BeginChild("conversation_sidebar", ImVec2(0, 0), true);
    ImGui::PopStyleColor(2);

    TextColor("Workspace", Rgba(246, 248, 251));
    TextMuted(Shorten(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_, 82));
    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    if (IconTextButton("conversation_open_builder", IconGlyph::Plus, "New Project", ImVec2(-1.0f, 36.0f), Rgba(32, 16, 20), Rgba(80, 31, 39), Rgba(248, 250, 252))) {
        active_nav_ = "projects";
        pending_popup_ = "Aegis Project Builder";
    }
    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    ImGui::Separator();
    ImGui::Dummy(ImVec2(0.0f, 10.0f));

    TextColor("Conversations", Rgba(246, 248, 251));
    ImGui::SameLine(ImGui::GetWindowWidth() - 52.0f);
    if (ImGui::SmallButton("...")) {
        RefreshConversationLibrary();
        pending_popup_ = "Aegis Conversations";
    }
    ImGui::Dummy(ImVec2(0.0f, 6.0f));

    ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(13, 16, 22));
    ImGui::PushStyleColor(ImGuiCol_FrameBgHovered, Rgba(24, 27, 34));
    ImGui::PushStyleColor(ImGuiCol_FrameBgActive, Rgba(32, 25, 30));
    ImGui::PushStyleColor(ImGuiCol_Border, Rgba(62, 64, 74));
    ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 8.0f);
    ImGui::InputTextWithHint("##conversation_sidebar_search", "Search chats or projects", conversation_search_buffer_.data(), conversation_search_buffer_.size());
    ImGui::PopStyleVar(2);
    ImGui::PopStyleColor(4);
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    const std::string filter = BufferString(conversation_search_buffer_.data());
    int visible = 0;
    if (!current_conversation_id_.empty() && !current_conversation_archived_) {
        const std::string current_title = current_conversation_title_.empty()
            ? ConversationTitleFromHistory(history_)
            : current_conversation_title_;
        const std::string current_preview = ConversationPreviewFromHistory(history_);
        if (filter.empty() ||
            ContainsCaseInsensitive(current_title, filter) ||
            ContainsCaseInsensitive(current_preview, filter)) {
            if (RowButton(
                    "conversation_row_current",
                    current_conversation_pinned_ ? IconGlyph::Shield : IconGlyph::Chat,
                    Shorten(current_title.empty() ? "Current chat" : current_title, 30).c_str(),
                    Shorten(current_preview.empty() ? "Current local conversation" : current_preview, 42).c_str(),
                    true)) {
                active_nav_ = "chat";
                status_ = "Current conversation is already open.";
            }
            ++visible;
        }
    }
    for (int i = 0; i < static_cast<int>(conversations_.size()); ++i) {
        const LocalConversationSummary& summary = conversations_[static_cast<size_t>(i)];
        if (summary.archived) {
            continue;
        }
        if (!current_conversation_id_.empty() && summary.id == current_conversation_id_) {
            continue;
        }
        if (!filter.empty() &&
            !ContainsCaseInsensitive(summary.title, filter) &&
            !ContainsCaseInsensitive(summary.preview, filter) &&
            !ContainsCaseInsensitive(summary.saved_at, filter)) {
            continue;
        }
        const std::string title = summary.title.empty() ? "Untitled conversation" : summary.title;
        const std::string subtitle = summary.preview.empty()
            ? (std::to_string(summary.message_count) + " messages")
            : summary.preview;
        if (RowButton(
                ("conversation_row_" + summary.id).c_str(),
                summary.pinned ? IconGlyph::Shield : IconGlyph::Chat,
                Shorten(title, 30).c_str(),
                Shorten(subtitle, 42).c_str(),
                summary.id == current_conversation_id_)) {
            LoadConversationFromLibrary(i);
            active_nav_ = "chat";
        }
        ++visible;
        if (visible >= 14) {
            break;
        }
    }

    if (visible == 0) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextMuted(filter.empty() ? "No previous conversations yet. The current chat is saved as soon as it has activity." : "No conversations match your search.");
    }

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    ImGui::Separator();
    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    TextColor("Project Signals", Rgba(246, 248, 251));
    const std::string active_model = models_.active_model.empty() ? config_.model_name : models_.active_model;
    TextMuted("Model: " + Shorten(active_model.empty() ? "Auto route" : active_model, 36));
    TextMuted("Mode: " + mode_);
    TextMuted("Queued: " + std::to_string(queued_user_messages_.size()));
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
    const bool profile_quick_actions = has_workspace_profile_snapshot_ && workspace_profile_.has_manifest;
    const float panel_width = ImGui::GetContentRegionAvail().x;
    const float panel_height = ImGui::GetContentRegionAvail().y;
    const float input_wrap_width = std::max(260.0f, panel_width - 128.0f);
    const std::string composer_text = std::string(message_buffer_.data());
    const float composer_text_height = ImGui::CalcTextSize(
        composer_text.empty() ? "Message Aegis AI..." : composer_text.c_str(),
        nullptr,
        false,
        input_wrap_width).y;
    const bool compact_composer = panel_width < 980.0f || panel_height < 760.0f;
    const float input_height = std::clamp(composer_text_height + 24.0f, 44.0f, compact_composer ? 96.0f : 132.0f);
    const float activity_line_height = 18.0f;
    const float raw_composer_height = 84.0f + input_height + activity_line_height +
        (attachments_.empty() ? 0.0f : 48.0f) +
        (cloud_context_warning ? 40.0f : 0.0f) +
        (profile_quick_actions ? 32.0f : 0.0f) +
        ((autopilot_enabled_ || autopilot_active_) ? 38.0f : 0.0f);
    const float composer_height = std::min(raw_composer_height, std::max(154.0f, panel_height * 0.42f));
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
            DrawSpinner(draw, ImVec2(pos.x + 24.0f, pos.y + 27.0f), 16.0f, 2.5f, Color(255, 255, 255, 0.09f), Color(248, 64, 82));
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 58.0f);
            TextColor("Aegis is working", Rgba(255, 120, 132));
            ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 58.0f);
            const std::string label = busy_label_.empty() ? "Preparing the next response" : busy_label_;
            TextMuted(label);
            const float dot_y = pos.y + 58.0f;
            for (int i = 0; i < 3; ++i) {
                const float dot = 0.35f + Pulse(4.0f, static_cast<float>(i) * 0.85f) * 0.65f;
                draw->AddRectFilled(ImVec2(pos.x + 58.0f + i * 13.0f, dot_y), ImVec2(pos.x + 64.0f + i * 13.0f, dot_y + 6.0f), Color(248, 64, 82, dot), 3.0f);
            }
            ImGui::SetCursorPos(ImVec2(ImGui::GetWindowWidth() - (autopilot_active_ ? 252.0f : 130.0f), 18.0f));
            if (autopilot_active_) {
                if (IconTextButton("autopilot_wrap_busy", IconGlyph::Shield, autopilot_stop_requested_ ? "Wrapping" : "Wrap Up", ImVec2(112.0f, 34.0f), Rgba(17, 25, 34), Rgba(34, 48, 61), autopilot_stop_requested_ ? Rgba(205, 154, 82) : Rgba(187, 222, 255))) {
                    RequestAutopilotWrapUp();
                }
                ImGui::SameLine();
            }
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
    const float composer_width = std::max(320.0f, ImGui::GetContentRegionAvail().x - 32.0f);
    ImGui::SetCursorPosX(ImGui::GetCursorPosX() + 16.0f);
    if (BeginCard("composer_card", ImVec2(composer_width, composer_height - 10.0f), true)) {
        ImGui::PushStyleColor(ImGuiCol_FrameBg, Rgba(0, 0, 0, 0));
        ImGui::PushStyleColor(ImGuiCol_Border, Rgba(0, 0, 0, 0));
        ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 0.0f);
        const bool submit_from_enter = ImGui::InputTextMultiline(
            "##composer",
            message_buffer_.data(),
            message_buffer_.size(),
            ImVec2(-1.0f, input_height),
            ImGuiInputTextFlags_AllowTabInput |
                ImGuiInputTextFlags_WordWrap |
                ImGuiInputTextFlags_NoHorizontalScroll |
                ImGuiInputTextFlags_EnterReturnsTrue |
                ImGuiInputTextFlags_CtrlEnterForNewLine);
        if (Trim(std::string(message_buffer_.data())).empty() && !ImGui::IsItemActive()) {
            const ImVec2 hint = ImGui::GetItemRectMin();
            ImGui::GetWindowDrawList()->AddText(ImVec2(hint.x + 4.0f, hint.y + 6.0f), Color(132, 142, 155), "Message Aegis AI...");
        }
        ImGui::PopStyleVar();
        ImGui::PopStyleColor(2);

        if (submit_from_enter && (!Trim(std::string(message_buffer_.data())).empty() || !attachments_.empty())) {
            workspace_root_ = BufferString(workspace_buffer_.data());
            SubmitMessage();
        }

        const std::string latest_activity = agent_activity_.empty()
            ? (status_.empty() ? "Ready." : status_)
            : (agent_activity_.back().message + " [" + agent_activity_.back().status + "]");
        TextMuted(Shorten(latest_activity, 140));

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
            ImGui::BeginChild("attachment_tray", ImVec2(0, 34.0f), false, ImGuiWindowFlags_HorizontalScrollbar);
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

        if (profile_quick_actions) {
            const WorkspaceProjectManifestInfo& manifest = workspace_profile_.manifest;
            const std::string project_title = manifest.title.empty() ? manifest.project_name : manifest.title;
            const std::string suggested_route = SuggestedRouteForWorkspaceProfile(manifest);
            ImGui::Dummy(ImVec2(0.0f, 3.0f));
            TextMuted("Project: " + Shorten(project_title.empty() ? "Aegis workspace" : project_title, 44) +
                " / " + Shorten(manifest.framework.empty() ? "manifest" : manifest.framework, 32));
            ImGui::SameLine();
            ImGui::BeginDisabled(busy_);
            if (ImGui::SmallButton("First Pass")) {
                SetBuffer(message_buffer_, BuildWorkspaceFirstPassPrompt(manifest));
                mode_ = "develop";
                run_validation_ = !manifest.validation_command.empty();
                status_ = "Loaded first-pass manifest prompt into the composer.";
            }
            ImGui::SameLine();
            ImGui::BeginDisabled(!has_workspace_autopilot_status_snapshot_ || !workspace_autopilot_status_.should_continue || workspace_autopilot_status_.suggested_prompt.empty());
            if (ImGui::SmallButton("Autopilot Next")) {
                SetBuffer(message_buffer_, workspace_autopilot_status_.suggested_prompt);
                mode_ = workspace_autopilot_status_.recommended_mode.empty() ? mode_ : workspace_autopilot_status_.recommended_mode;
                run_validation_ = workspace_autopilot_status_.run_validation || run_validation_;
                max_repairs_ = std::max(max_repairs_, workspace_autopilot_status_.max_repair_attempts);
                status_ = "Loaded backend autopilot next action.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            if (ImGui::SmallButton(RouteLabelForWorkspaceProfile(suggested_route).c_str())) {
                StartCodingRoute(suggested_route);
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(manifest.install_command.empty());
            if (ImGui::SmallButton("Copy Install")) {
                ImGui::SetClipboardText(manifest.install_command.c_str());
                status_ = "Copied install command.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(manifest.validation_command.empty());
            if (ImGui::SmallButton("Use Validate")) {
                SetBuffer(validation_command_buffer_, manifest.validation_command);
                SetBuffer(validation_label_buffer_, (manifest.preset_label.empty() ? "Workspace" : manifest.preset_label) + " validation");
                SetBuffer(validation_notes_buffer_, "Loaded from .aegis/project.json.");
                run_validation_ = true;
                status_ = "Validation command loaded from workspace profile.";
            }
            ImGui::EndDisabled();
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
            ImGui::SliderInt("Repairs", &max_repairs_, 0, 5);
            if (ImGui::IsItemHovered()) {
                ImGui::SetTooltip("Automatic validation repair attempts after a failed validation run.");
            }
        }
        if (ImGui::GetWindowWidth() > 900.0f) {
            ImGui::SameLine(0.0f, 18.0f);
            if (ImGui::Checkbox("Autopilot", &autopilot_enabled_)) {
                if (!autopilot_enabled_ && autopilot_active_) {
                    RequestAutopilotWrapUp();
                } else {
                    RefreshAutopilotSuggestions();
                }
            }
            if (ImGui::IsItemHovered()) {
                ImGui::SetTooltip("Keep working through plan, build, validation, and repair passes until a clean handoff point.");
            }
        }
        if (ImGui::GetWindowWidth() > 1020.0f) {
            ImGui::SameLine(0.0f, 18.0f);
            TextMuted("Workspace: " + Shorten(active_workspace.empty() ? "not selected" : active_workspace, 54));
        }

        if (autopilot_enabled_ || autopilot_active_) {
            ImGui::Dummy(ImVec2(0.0f, 3.0f));
            const std::string autopilot_state = autopilot_active_
                ? ("Autopilot: pass " + std::to_string(autopilot_rounds_completed_) + "/" + std::to_string(autopilot_max_rounds_) +
                    (autopilot_stop_requested_ ? " / wrapping up" : " / running"))
                : "Autopilot armed. Send still works, or start from the latest goal.";
            TextMuted(autopilot_state);
            ImGui::SameLine(0.0f, 12.0f);
            ImGui::SetNextItemWidth(132.0f);
            ImGui::SliderInt("Passes", &autopilot_max_rounds_, 3, kAutopilotMaxPassLimit);
            autopilot_max_rounds_ = std::max(autopilot_min_rounds_, autopilot_max_rounds_);
            if (autopilot_active_) {
                ImGui::SameLine(0.0f, 12.0f);
                if (ImGui::SmallButton(autopilot_stop_requested_ ? "Wrapping Up" : "Wrap Up")) {
                    RequestAutopilotWrapUp();
                }
            } else {
                ImGui::SameLine(0.0f, 12.0f);
                ImGui::BeginDisabled(busy_);
                if (ImGui::SmallButton("Start Now")) {
                    StartAutopilotFromCurrentContext();
                }
                ImGui::EndDisabled();
            }
            if (!autopilot_suggestions_.empty()) {
                ImGui::Dummy(ImVec2(0.0f, 2.0f));
                TextMuted("Suggestions: " + Shorten(JoinList(autopilot_suggestions_, " / "), 170));
            }
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
        if (ImGui::GetWindowWidth() > 660.0f) {
            ImGui::SameLine();
            ImGui::BeginDisabled(busy_);
            if (IconTextButton("composer_route", IconGlyph::Sliders, "Route", ImVec2(96.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
                PreviewComposerRoute();
            }
            ImGui::EndDisabled();
            if (ImGui::IsItemHovered()) {
                ImGui::SetTooltip("Preview the selected role, model route, context budget, and route-health signal.");
            }
        }

        const float send_x = ImGui::GetWindowWidth() - 56.0f;
        if (ImGui::GetCursorPosX() + 52.0f < send_x) {
            ImGui::SameLine(send_x);
        } else {
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
            ImGui::SetCursorPosX(send_x);
        }
        const bool can_queue_autopilot_instruction =
            busy_ &&
            autopilot_active_ &&
            (!Trim(std::string(message_buffer_.data())).empty() || !attachments_.empty());
        const bool can_submit_or_queue =
            !Trim(std::string(message_buffer_.data())).empty() ||
            !attachments_.empty() ||
            can_queue_autopilot_instruction;
        ImGui::BeginDisabled(!can_submit_or_queue);
        if (IconOnlyButton("send_message", IconGlyph::Send, ImVec2(40.0f, 40.0f), Rgba(210, 39, 55), Rgba(239, 68, 68), Rgba(255, 255, 255))) {
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

void AegisChatApp::RenderAgentActivityPanel()
{
    const auto activity_color = [](const std::string& status) {
        if (status == "success" || status == "passed" || status == "succeeded") {
            return Rgba(58, 217, 127);
        }
        if (status == "failed" || status == "error") {
            return Rgba(248, 113, 113);
        }
        if (status == "warning" || status == "pending" || status == "skipped") {
            return Rgba(234, 179, 85);
        }
        return Rgba(255, 120, 132);
    };

    if (BeginCard("agent_activity_card", ImVec2(0, 306.0f))) {
        TextColor("Agent Activity", Rgba(246, 248, 251));
        ImGui::SameLine(ImGui::GetWindowWidth() - 126.0f);
        const std::string state = connection_state_.empty() ? "offline" : connection_state_;
        TextColor(state == "connected" ? "Connected" : (state == "reconnecting" ? "Reconnecting" : (state == "failed" ? "Failed" : "Offline")),
                  state == "connected" ? Rgba(58, 217, 127) : activity_color(state == "failed" ? "failed" : "warning"));
        ImGui::Separator();
        TextMuted(connection_detail_.empty() ? status_ : connection_detail_);
        if (!queued_user_messages_.empty()) {
            TextColor(std::to_string(queued_user_messages_.size()) + " queued prompt(s)", Rgba(234, 179, 85));
        }
        ImGui::Dummy(ImVec2(0.0f, 6.0f));

        ImGui::BeginChild("agent_activity_log", ImVec2(0, 206.0f), false);
        if (agent_activity_.empty()) {
            TextMuted("Activity events will appear here while Aegis scans, plans, edits, validates, and repairs.");
        } else {
            const int start = std::max(0, static_cast<int>(agent_activity_.size()) - 12);
            for (int i = start; i < static_cast<int>(agent_activity_.size()); ++i) {
                const AgentActivityEvent& event = agent_activity_[static_cast<size_t>(i)];
                ImGui::PushID(i);
                const ImVec4 color = activity_color(event.status);
                TextColor("[" + event.timestamp + "] " + Shorten(event.type, 12), color);
                TextMuted(event.message);
                if (!event.file_path.empty()) {
                    TextMuted("file: " + event.file_path);
                }
                if (!event.command.empty()) {
                    TextMuted("cmd: " + event.command);
                }
                if (i + 1 < static_cast<int>(agent_activity_.size())) {
                    ImGui::Dummy(ImVec2(0.0f, 4.0f));
                }
                ImGui::PopID();
            }
            if (busy_ || !queued_user_messages_.empty()) {
                ImGui::SetScrollHereY(1.0f);
            }
        }
        ImGui::EndChild();
    }
    EndCard();
}

void AegisChatApp::RenderRightPanel()
{
    ImGui::PushStyleColor(ImGuiCol_ChildBg, Rgba(0, 0, 0, 0));
    ImGui::BeginChild("right_panel", ImVec2(0, 0), false);
    ImGui::PopStyleColor();
    ImGui::Dummy(ImVec2(0.0f, 2.0f));

    RenderAgentActivityPanel();
    ImGui::Dummy(ImVec2(0.0f, 4.0f));

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
    const bool has_route_timeline =
        has_response_ &&
        (last_response_.has_task_plan || last_response_.has_context_budget || !last_response_.model_attempts.empty());
    const bool has_preview_timeline =
        !has_route_timeline &&
        has_route_preview_ &&
        (route_preview_.has_task_plan || route_preview_.has_context_budget || !route_preview_.model_attempts.empty());
    if (has_route_timeline || has_preview_timeline) {
        if (BeginCard("route_timeline_card", ImVec2(0, 254.0f))) {
            RenderRouteTimelineCard(has_route_timeline ? last_response_ : route_preview_, has_preview_timeline);
        }
        EndCard();
    } else {
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
    }

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
                if (IconTextButton("apply_snapshot_changes", IconGlyph::Bolt, fully_applied ? "Applied" : "Apply Changes", ImVec2(-1.0f, 38.0f), Rgba(210, 39, 55), Rgba(239, 68, 68), Rgba(255, 255, 255))) {
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
            RecordFeedback("liked", last_response_.reply, "response_tab; task_id=" + last_response_.task_id, "response_feedback", "assistant_response", last_response_.engine);
        }
        ImGui::SameLine();
        if (ImGui::Button("Reject Response")) {
            RecordFeedback("disliked", last_response_.reply, "response_tab; task_id=" + last_response_.task_id, "response_feedback", "assistant_response", last_response_.engine);
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
            RecordFeedback("liked", validation_payload, "validation_result; task_id=" + last_response_.task_id, "validation_feedback", "validation_result", last_response_.engine);
        }
        ImGui::SameLine();
        if (ImGui::Button("Bad Validation")) {
            RecordFeedback("disliked", validation_payload, "validation_result; task_id=" + last_response_.task_id, "validation_feedback", "validation_result", last_response_.engine);
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

void AegisChatApp::RenderRouteTimelineCard(const AgentResponse& response, bool preview_mode)
{
    TextColor(preview_mode ? "Route Preview" : "Route Timeline", Rgba(246, 248, 251));
    ImGui::SameLine(ImGui::GetWindowWidth() - 116.0f);
    ImGui::BeginDisabled(busy_);
    if (IconTextButton("route_planning_history", IconGlyph::History, "History", ImVec2(92.0f, 28.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
        RefreshTelemetry();
        pending_popup_ = "Aegis Planning History";
        status_ = "Opened planning history.";
    }
    ImGui::EndDisabled();
    ImGui::Separator();

    const bool has_metadata =
        response.has_task_plan || response.has_context_budget || !response.model_attempts.empty();
    if (!has_metadata) {
        TextMuted(preview_mode ? "Type a prompt and preview its route." : "Routing metadata will appear after the next planned response.");
        return;
    }

    const auto privacy_color = [](const std::string& privacy) {
        const std::string lowered = Lower(privacy);
        if (lowered.find("cloud") != std::string::npos || lowered.find("remote") != std::string::npos) {
            return Rgba(205, 154, 82);
        }
        if (lowered.find("local") != std::string::npos) {
            return Rgba(38, 221, 123);
        }
        return Rgba(151, 160, 171);
    };
    const auto status_color = [](const std::string& status) {
        const std::string lowered = Lower(status);
        if (lowered == "succeeded") {
            return Rgba(38, 221, 123);
        }
        if (lowered == "failed" || lowered == "canceled") {
            return Rgba(248, 113, 113);
        }
        if (lowered == "running" || lowered == "fallback") {
            return Rgba(205, 154, 82);
        }
        return Rgba(151, 160, 171);
    };

    if (response.has_task_plan) {
        const TaskPlanInfo& plan = response.task_plan;
        const RoutingDecisionInfo& route = plan.routing;
        std::string role = plan.has_routing && !route.task_role.empty() ? route.task_role : plan.intent;
        if (role.empty()) {
            role = "general";
        }
        std::string provider = plan.has_routing ? route.provider_hint : "";
        if (provider.empty() && plan.has_routing && !route.candidates.empty()) {
            provider = route.candidates.front().provider_hint;
        }
        if (provider.empty()) {
            provider = config_.model_api.empty() ? "local" : config_.model_api;
        }
        const std::string privacy = plan.has_routing ? route.privacy_mode : "local-first";
        TextColor(Shorten(role, 34), Rgba(246, 248, 251));
        ImGui::SameLine();
        Pill(Shorten(privacy, 16).c_str(), privacy_color(privacy));
        const std::string profile_label = plan.route_profile.label.empty() ? plan.route_profile.id : plan.route_profile.label;
        if (!profile_label.empty()) {
            ImGui::SameLine();
            Pill(Shorten(profile_label, 18).c_str(), Rgba(88, 166, 255));
        }
        TextMuted("Provider: " + Shorten(provider, 34));
        if (!profile_label.empty()) {
            std::string profile_text = "Profile: " + profile_label;
            if (!plan.route_profile.category.empty()) {
                profile_text += " / " + plan.route_profile.category;
            }
            if (!plan.route_profile.reason.empty()) {
                profile_text += " - " + plan.route_profile.reason;
            }
            TextMuted(Shorten(profile_text, 96));
        }
        const std::string objective = !plan.objective.empty() ? plan.objective : plan.workflow;
        if (!objective.empty()) {
            TextMuted(Shorten(objective, 96));
        }
        if (plan.has_routing && !route.summary.empty()) {
            TextMuted("Decision: " + Shorten(route.summary, 88));
        }
    }

    if (response.has_context_budget) {
        const ContextBudgetInfo& budget = response.context_budget;
        const int requested_tokens = budget.estimated_context_tokens + budget.reserve_response_tokens;
        const float fraction = budget.max_context_tokens > 0
            ? Clamp01(static_cast<float>(requested_tokens) / static_cast<float>(budget.max_context_tokens))
            : 0.0f;
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        DrawProgress(fraction, ImVec2(ImGui::GetContentRegionAvail().x, 6.0f), fraction > 0.72f);
        TextMuted("Context: " + std::to_string(budget.estimated_context_tokens) + " used + " +
            std::to_string(budget.reserve_response_tokens) + " reserved / " +
            (budget.max_context_tokens > 0 ? std::to_string(budget.max_context_tokens) : std::string("unknown")) + " tokens");
        TextMuted("Files: " + std::to_string(budget.selected_file_count) + " / " +
            std::to_string(budget.workspace_file_count) + " selected, " +
            std::to_string(budget.omitted_file_count) + " omitted");
        const int memory_count = budget.selected_memory_count + budget.selected_project_memory_count;
        const int omitted_memory = budget.omitted_memory_count + budget.omitted_project_memory_count;
        TextMuted("Memory: " + std::to_string(memory_count) + " selected, " +
            std::to_string(omitted_memory) + " omitted");
    }

    if (!response.model_attempts.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        if (ImGui::BeginTable(preview_mode ? "route_preview_attempts_table" : "route_attempts_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Try", ImGuiTableColumnFlags_WidthFixed, 42.0f);
            ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 76.0f);
            ImGui::TableSetupColumn("Model");
            ImGui::TableSetupColumn("Quality", ImGuiTableColumnFlags_WidthFixed, 86.0f);
            ImGui::TableSetupColumn("Budget", ImGuiTableColumnFlags_WidthFixed, 96.0f);
            ImGui::TableHeadersRow();
            const int count = std::min(3, static_cast<int>(response.model_attempts.size()));
            for (int i = 0; i < count; ++i) {
                const ModelAttemptInfo& attempt = response.model_attempts[i];
                const std::string provider = attempt.provider_label.empty() ? attempt.provider_id : attempt.provider_label;
                const std::string model = attempt.model.empty() ? provider : (provider.empty() ? attempt.model : provider + " / " + attempt.model);
                const std::string status = attempt.status.empty() ? "planned" : attempt.status;
                std::string budget_text = FormatOptionalInt(attempt.input_tokens, attempt.has_input_tokens) + "/" +
                    FormatOptionalInt(attempt.output_tokens, attempt.has_output_tokens);
                if (attempt.has_estimated_cost) {
                    budget_text += " " + FormatCostUsd(attempt.estimated_cost_usd, true);
                }
                std::string quality_text = FormatPercent(attempt.benchmark_suite_score, attempt.has_benchmark_suite_score);
                ImVec4 quality_color = Rgba(151, 160, 171);
                if (attempt.route_health_cooldown) {
                    quality_text = "Cooldown";
                    quality_color = Rgba(248, 113, 113);
                } else if (attempt.has_route_health_penalty && attempt.route_health_penalty > 0.0) {
                    quality_text = "Health -" + FormatNumber(attempt.route_health_penalty, true, 0);
                    quality_color = Rgba(205, 154, 82);
                } else if (attempt.has_route_health_failure_rate && attempt.route_health_failure_rate > 0.0) {
                    quality_text = "Fail " + FormatPercent(attempt.route_health_failure_rate);
                    quality_color = Rgba(205, 154, 82);
                } else if (attempt.structured_preview_retired) {
                    quality_text = "Preview reset";
                    quality_color = Rgba(205, 154, 82);
                } else if (attempt.structured_preview_final_winner) {
                    quality_text = "Stream win";
                    quality_color = Rgba(68, 212, 146);
                } else if (attempt.structured_preview_emitted) {
                    quality_text = "Previewed";
                    quality_color = Rgba(84, 186, 255);
                }

                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextMuted(std::to_string(attempt.attempt > 0 ? attempt.attempt : i + 1));
                ImGui::TableSetColumnIndex(1);
                Pill(Shorten(status, 9).c_str(), status_color(status));
                ImGui::TableSetColumnIndex(2);
                TextMuted(Shorten(model.empty() ? attempt.role : model, 38));
                ImGui::TableSetColumnIndex(3);
                TextColor(Shorten(quality_text, 14), quality_color);
                ImGui::TableSetColumnIndex(4);
                TextMuted(Shorten(budget_text, 24));
            }
            ImGui::EndTable();
        }
        if (response.model_attempts.size() > 3) {
            TextMuted("Showing 3 of " + std::to_string(response.model_attempts.size()) + " planned model attempt(s).");
        }
    }

    if (!response.routing_recommendations.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        const int count = std::min(2, static_cast<int>(response.routing_recommendations.size()));
        for (int i = 0; i < count; ++i) {
            TextMuted(Shorten(response.routing_recommendations[i], 92));
        }
    }
}

void AegisChatApp::RenderPlanningHistoryModal()
{
    TextColor("Planning History", Rgba(246, 248, 251));
    TextMuted("Recent context budgets and model routing attempts for this workspace.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    ImGui::BeginDisabled(busy_);
    if (IconTextButton("planning_history_refresh", IconGlyph::History, "Refresh", ImVec2(120.0f, 34.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(232, 238, 245))) {
        RefreshTelemetry();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    TextMuted(telemetry_.workspace_root.empty()
        ? Trim(workspace_root_.empty() ? BufferString(workspace_buffer_.data()) : workspace_root_)
        : telemetry_.workspace_root);
    ImGui::Separator();

    if (!telemetry_loaded_) {
        TextMuted("Open this panel from the route timeline or refresh to load planning telemetry.");
        return;
    }

    double total_estimated_cost = 0.0;
    int succeeded_attempts = 0;
    int failed_attempts = 0;
    for (const ModelAttemptTelemetryEntryInfo& entry : telemetry_.model_attempts) {
        const ModelAttemptInfo& attempt = entry.attempt;
        if (attempt.has_estimated_cost) {
            total_estimated_cost += attempt.estimated_cost_usd;
        }
        const std::string status = Lower(attempt.status);
        if (status == "succeeded") {
            ++succeeded_attempts;
        } else if (status == "failed" || status == "canceled") {
            ++failed_attempts;
        }
    }

    ImGui::Columns(4, "planning_history_summary", false);
    TextMuted("Budgets");
    TextColor(std::to_string(telemetry_.context_budgets.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Attempts");
    TextColor(std::to_string(telemetry_.model_attempts.size()), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Succeeded / Failed");
    TextColor(std::to_string(succeeded_attempts) + " / " + std::to_string(failed_attempts), Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Est. Cost");
    TextColor(FormatCostUsd(total_estimated_cost, total_estimated_cost > 0.0), Rgba(246, 248, 251));
    ImGui::Columns(1);

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    TextColor("Route Quality", Rgba(246, 248, 251));
    if (route_quality_loaded_) {
        const RouteQualityOverviewInfo& overview = route_quality_.overview;
        const ImVec4 reliability_color = overview.reliability_score >= 80.0
            ? Rgba(38, 221, 123)
            : (overview.reliability_score >= 55.0 ? Rgba(205, 154, 82) : Rgba(248, 113, 113));
        ImGui::Columns(6, "route_quality_summary", false);
        TextMuted("Reliability");
        TextColor(FormatNumber(overview.reliability_score, true, 1), reliability_color);
        ImGui::NextColumn();
        TextMuted("Success");
        TextColor(FormatPercent(overview.success_rate), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Fallback");
        TextColor(FormatPercent(overview.fallback_rate), overview.fallback_rate > 0.25 ? Rgba(205, 154, 82) : Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Context");
        TextColor(FormatPercent(overview.average_context_utilization, overview.has_average_context_utilization), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Spend");
        TextColor(FormatCostUsd(overview.estimated_cost_usd, overview.estimated_cost_usd > 0.0), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Feedback");
        TextColor(
            std::to_string(overview.positive_feedback) + " / " + std::to_string(overview.negative_feedback),
            overview.negative_feedback > overview.positive_feedback ? Rgba(248, 113, 113) : Rgba(246, 248, 251));
        ImGui::Columns(1);

        if (!route_quality_.recommendations.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            const int recommendation_count = std::min(2, static_cast<int>(route_quality_.recommendations.size()));
            for (int i = 0; i < recommendation_count; ++i) {
                TextMuted(Shorten(route_quality_.recommendations[static_cast<size_t>(i)], 136));
            }
        }

        const auto context_util_color = [](double utilization, bool present) {
            if (!present) {
                return Rgba(151, 160, 171);
            }
            if (utilization >= 0.92) {
                return Rgba(248, 113, 113);
            }
            if (utilization >= 0.76) {
                return Rgba(205, 154, 82);
            }
            return Rgba(38, 221, 123);
        };
        const auto context_route_label = [](const std::string& role, const std::string& intent) {
            if (!role.empty() && !intent.empty() && role != intent) {
                return role + " / " + intent;
            }
            if (!role.empty()) {
                return role;
            }
            return intent.empty() ? std::string("general") : intent;
        };
        const auto calibration_status_color = [](const std::string& status) {
            const std::string lowered = Lower(status);
            if (lowered == "stable") {
                return Rgba(38, 221, 123);
            }
            if (lowered == "watch") {
                return Rgba(205, 154, 82);
            }
            if (lowered == "drift") {
                return Rgba(248, 113, 113);
            }
            return Rgba(151, 160, 171);
        };
        const auto calibration_trend_color = [](const std::string& direction) {
            const std::string lowered = Lower(direction);
            if (lowered == "improving") {
                return Rgba(38, 221, 123);
            }
            if (lowered == "worsening") {
                return Rgba(248, 113, 113);
            }
            if (lowered == "flat" || lowered == "baseline") {
                return Rgba(205, 154, 82);
            }
            return Rgba(151, 160, 171);
        };
        const auto structured_preview_status_color = [](const std::string& status) {
            const std::string lowered = Lower(status);
            if (lowered == "stable") {
                return Rgba(38, 221, 123);
            }
            if (lowered == "unstable") {
                return Rgba(248, 113, 113);
            }
            if (lowered == "watch") {
                return Rgba(205, 154, 82);
            }
            return Rgba(151, 160, 171);
        };

        if (!route_quality_.contexts.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Context Pressure");
            if (ImGui::BeginTable("route_quality_context_pressure_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Route");
                ImGui::TableSetupColumn("Budgets", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Utilization", ImGuiTableColumnFlags_WidthFixed, 94.0f);
                ImGui::TableSetupColumn("Avg Tokens", ImGuiTableColumnFlags_WidthFixed, 96.0f);
                ImGui::TableSetupColumn("File Tokens", ImGuiTableColumnFlags_WidthFixed, 92.0f);
                ImGui::TableSetupColumn("Files", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(6, static_cast<int>(route_quality_.contexts.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityContextRollupInfo& context = route_quality_.contexts[static_cast<size_t>(i)];
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(context_route_label(context.route_role, context.intent), 42), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(std::to_string(context.budget_count));
                    ImGui::TableSetColumnIndex(2);
                    TextColor(
                        FormatPercent(context.average_budget_utilization, context.has_average_budget_utilization),
                        context_util_color(context.average_budget_utilization, context.has_average_budget_utilization));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(FormatNumber(context.average_context_tokens, context.budget_count > 0, 0));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(FormatNumber(context.average_file_tokens, context.budget_count > 0, 0));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(
                        FormatNumber(context.average_selected_files, context.budget_count > 0, 1) +
                        " / " +
                        FormatNumber(context.average_omitted_files, context.budget_count > 0, 1));
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.token_calibration.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Token Calibration");
            if (ImGui::BeginTable("route_quality_token_calibration_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Provider");
                ImGui::TableSetupColumn("Model");
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 76.0f);
                ImGui::TableSetupColumn("Samples", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Avg Error", ImGuiTableColumnFlags_WidthFixed, 104.0f);
                ImGui::TableSetupColumn("Est / Reported", ImGuiTableColumnFlags_WidthFixed, 146.0f);
                ImGui::TableSetupColumn("Source", ImGuiTableColumnFlags_WidthFixed, 118.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(6, static_cast<int>(route_quality_.token_calibration.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityTokenCalibrationInfo& calibration = route_quality_.token_calibration[static_cast<size_t>(i)];
                    const std::string provider_label = calibration.provider_label.empty() ? calibration.provider_id : calibration.provider_label;
                    const std::string avg_error =
                        "I " + FormatPercent(calibration.average_input_token_error, calibration.has_average_input_token_error) +
                        " / O " + FormatPercent(calibration.average_output_token_error, calibration.has_average_output_token_error);
                    const std::string token_delta =
                        "I " + std::to_string(calibration.estimated_input_tokens) + "/" + std::to_string(calibration.reported_input_tokens) +
                        " O " + std::to_string(calibration.estimated_output_tokens) + "/" + std::to_string(calibration.reported_output_tokens);
                    const std::string source = !calibration.reported_token_sources.empty()
                        ? calibration.reported_token_sources.front()
                        : (calibration.token_estimator_sources.empty() ? std::string("-") : calibration.token_estimator_sources.front());

                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(provider_label.empty() ? "unknown" : provider_label, 28), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(calibration.model.empty() ? "-" : calibration.model, 30));
                    ImGui::TableSetColumnIndex(2);
                    TextColor(Shorten(calibration.calibration_status.empty() ? "insufficient" : calibration.calibration_status, 16), calibration_status_color(calibration.calibration_status));
                    if (ImGui::IsItemHovered()) {
                        std::string tooltip = calibration.recommendation.empty() ? "No calibration recommendation recorded." : calibration.recommendation;
                        if (!calibration.reported_token_sources.empty()) {
                            tooltip += "\nReported: " + JoinList(calibration.reported_token_sources);
                        }
                        if (!calibration.token_estimator_sources.empty()) {
                            tooltip += "\nEstimated: " + JoinList(calibration.token_estimator_sources);
                        }
                        ImGui::SetTooltip("%s", tooltip.c_str());
                    }
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(std::to_string(calibration.calibrated_attempts) + " / " + std::to_string(calibration.attempts));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(avg_error);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(token_delta);
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(source, 24));
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.token_calibration_trends.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Calibration Trend");
            if (ImGui::BeginTable("route_quality_token_calibration_trend_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Period", ImGuiTableColumnFlags_WidthFixed, 84.0f);
                ImGui::TableSetupColumn("Provider");
                ImGui::TableSetupColumn("Model");
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 76.0f);
                ImGui::TableSetupColumn("Trend", ImGuiTableColumnFlags_WidthFixed, 88.0f);
                ImGui::TableSetupColumn("Samples", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Avg Error", ImGuiTableColumnFlags_WidthFixed, 108.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(6, static_cast<int>(route_quality_.token_calibration_trends.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityTokenCalibrationTrendInfo& trend = route_quality_.token_calibration_trends[static_cast<size_t>(i)];
                    const std::string provider_label = trend.provider_label.empty() ? trend.provider_id : trend.provider_label;
                    const std::string avg_error =
                        "I " + FormatPercent(trend.average_input_token_error, trend.has_average_input_token_error) +
                        " / O " + FormatPercent(trend.average_output_token_error, trend.has_average_output_token_error);
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(Shorten(trend.period_start.empty() ? "unknown" : trend.period_start, 14));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(provider_label.empty() ? "unknown" : provider_label, 26), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(trend.model.empty() ? "-" : trend.model, 28));
                    ImGui::TableSetColumnIndex(3);
                    TextColor(Shorten(trend.calibration_status.empty() ? "insufficient" : trend.calibration_status, 16), calibration_status_color(trend.calibration_status));
                    ImGui::TableSetColumnIndex(4);
                    TextColor(Shorten(trend.trend_direction.empty() ? "baseline" : trend.trend_direction, 18), calibration_trend_color(trend.trend_direction));
                    if (ImGui::IsItemHovered()) {
                        const std::string tooltip = trend.recommendation.empty() ? "No trend recommendation recorded." : trend.recommendation;
                        ImGui::SetTooltip("%s", tooltip.c_str());
                    }
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(std::to_string(trend.calibrated_attempts) + " / " + std::to_string(trend.attempts));
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(avg_error);
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.structured_preview.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Structured Preview Reliability");
            if (ImGui::BeginTable("route_quality_structured_preview_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Provider");
                ImGui::TableSetupColumn("Model");
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Final", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Retired", ImGuiTableColumnFlags_WidthFixed, 76.0f);
                ImGui::TableSetupColumn("Resets", ImGuiTableColumnFlags_WidthFixed, 64.0f);
                ImGui::TableSetupColumn("Preview", ImGuiTableColumnFlags_WidthFixed, 118.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(6, static_cast<int>(route_quality_.structured_preview.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityStructuredPreviewInfo& preview = route_quality_.structured_preview[static_cast<size_t>(i)];
                    const std::string provider_label = preview.provider_label.empty() ? preview.provider_id : preview.provider_label;
                    const std::string final_text = std::to_string(preview.final_winning_attempts) + " / " + std::to_string(preview.previewed_attempts);
                    const std::string retired_text = std::to_string(preview.retired_attempts) + " / " + std::to_string(preview.previewed_attempts);
                    const std::string preview_text = std::to_string(preview.delta_count) + "d / " + std::to_string(preview.char_count) + "ch";
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(provider_label.empty() ? "unknown" : provider_label, 28), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(preview.model.empty() ? "-" : preview.model, 30));
                    ImGui::TableSetColumnIndex(2);
                    TextColor(Shorten(preview.preview_status.empty() ? "insufficient" : preview.preview_status, 16), structured_preview_status_color(preview.preview_status));
                    if (ImGui::IsItemHovered()) {
                        std::string tooltip = preview.recommendation.empty() ? "No structured preview recommendation recorded." : preview.recommendation;
                        if (!preview.retired_reasons.empty()) {
                            tooltip += "\nRetired: " + JoinList(preview.retired_reasons);
                        }
                        ImGui::SetTooltip("%s", tooltip.c_str());
                    }
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(final_text);
                    ImGui::TableSetColumnIndex(4);
                    TextColor(retired_text, preview.retired_attempts > 0 ? Rgba(205, 154, 82) : Rgba(151, 160, 171));
                    ImGui::TableSetColumnIndex(5);
                    TextColor(std::to_string(preview.reset_count), preview.reset_count > 0 ? Rgba(248, 113, 113) : Rgba(151, 160, 171));
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(preview_text);
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.context_drilldowns.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Context Drilldowns");
            if (ImGui::BeginTable("route_quality_context_drilldowns_table", 8, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Created", ImGuiTableColumnFlags_WidthFixed, 116.0f);
                ImGui::TableSetupColumn("Task", ImGuiTableColumnFlags_WidthFixed, 92.0f);
                ImGui::TableSetupColumn("Route");
                ImGui::TableSetupColumn("Util", ImGuiTableColumnFlags_WidthFixed, 64.0f);
                ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 112.0f);
                ImGui::TableSetupColumn("Files", ImGuiTableColumnFlags_WidthFixed, 72.0f);
                ImGui::TableSetupColumn("Largest Refs");
                ImGui::TableSetupColumn("Recommendation");
                ImGui::TableHeadersRow();
                const int count = std::min(8, static_cast<int>(route_quality_.context_drilldowns.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityContextDrilldownInfo& drilldown = route_quality_.context_drilldowns[static_cast<size_t>(i)];
                    const int reserved_tokens = drilldown.estimated_context_tokens + drilldown.reserve_response_tokens;
                    const std::string token_text =
                        std::to_string(reserved_tokens) + " / " +
                        (drilldown.max_context_tokens > 0 ? std::to_string(drilldown.max_context_tokens) : std::string("-"));
                    const int selected_memories = drilldown.selected_memory_count + drilldown.selected_project_memory_count;
                    const int omitted_memories = drilldown.omitted_memory_count + drilldown.omitted_project_memory_count;
                    std::string file_text =
                        std::to_string(drilldown.selected_file_count) + " / " +
                        std::to_string(drilldown.omitted_file_count);
                    if ((selected_memories + omitted_memories) > 0) {
                        file_text += " | M " + std::to_string(selected_memories) + " / " + std::to_string(omitted_memories);
                    }
                    const std::vector<std::string>& refs = drilldown.largest_refs.empty()
                        ? drilldown.selected_refs
                        : drilldown.largest_refs;
                    std::string recommendation = drilldown.recommendations.empty()
                        ? (drilldown.notes.empty() ? std::string() : drilldown.notes.front())
                        : drilldown.recommendations.front();
                    if (recommendation.empty() && omitted_memories > 0) {
                        recommendation = std::to_string(omitted_memories) + " memory item(s) were omitted.";
                    }

                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(CompactTimestamp(drilldown.created_at));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(drilldown.task_id.empty() ? "-" : drilldown.task_id, 12));
                    ImGui::TableSetColumnIndex(2);
                    TextColor(Shorten(context_route_label(drilldown.route_role, drilldown.intent), 38), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(3);
                    TextColor(FormatPercent(drilldown.utilization, drilldown.has_utilization), context_util_color(drilldown.utilization, drilldown.has_utilization));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(token_text);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(file_text);
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(refs.empty() ? "-" : JoinList(refs), 46));
                    ImGui::TableSetColumnIndex(7);
                    TextMuted(Shorten(recommendation.empty() ? "-" : recommendation, 68));
                }
                ImGui::EndTable();
            }
        }

        const auto feedback_color = [](const std::string& value) {
            const std::string lowered = Lower(value);
            if (lowered == "liked" || lowered == "accepted" || lowered == "copied") {
                return Rgba(38, 221, 123);
            }
            if (lowered == "disliked" || lowered == "rejected" || lowered == "rolled_back") {
                return Rgba(248, 113, 113);
            }
            if (lowered == "revised" || lowered == "regenerated" || lowered == "corrected") {
                return Rgba(205, 154, 82);
            }
            return Rgba(151, 160, 171);
        };

        if (!route_quality_.feedback_rollups.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Feedback Outcomes");
            if (ImGui::BeginTable("route_quality_feedback_rollups_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Dimension", ImGuiTableColumnFlags_WidthFixed, 92.0f);
                ImGui::TableSetupColumn("Key");
                ImGui::TableSetupColumn("Events", ImGuiTableColumnFlags_WidthFixed, 64.0f);
                ImGui::TableSetupColumn("Positive", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Negative", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Signals", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(6, static_cast<int>(route_quality_.feedback_rollups.size()));
                for (int i = 0; i < count; ++i) {
                    const FeedbackAttributionRollupInfo& rollup = route_quality_.feedback_rollups[static_cast<size_t>(i)];
                    const std::string label = rollup.label.empty() ? rollup.key : rollup.label;
                    const std::string signals =
                        "A " + std::to_string(rollup.applied_count) +
                        " / R " + std::to_string(rollup.rolled_back_count) +
                        " / C " + std::to_string(rollup.corrected_count);
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(Shorten(rollup.dimension.empty() ? "unknown" : rollup.dimension, 18));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(label.empty() ? "unknown" : label, 42), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(std::to_string(rollup.feedback_count));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(FormatPercent(rollup.positive_rate));
                    ImGui::TableSetColumnIndex(4);
                    TextColor(FormatPercent(rollup.negative_rate), rollup.negative_rate >= 0.30 ? Rgba(248, 113, 113) : Rgba(151, 160, 171));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(signals);
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.feedback_trends.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Feedback Trend");
            if (ImGui::BeginTable("route_quality_feedback_trends_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Period", ImGuiTableColumnFlags_WidthFixed, 92.0f);
                ImGui::TableSetupColumn("Events", ImGuiTableColumnFlags_WidthFixed, 64.0f);
                ImGui::TableSetupColumn("Positive", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Negative", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Apply/Rollback", ImGuiTableColumnFlags_WidthFixed, 118.0f);
                ImGui::TableSetupColumn("Regen/Correct", ImGuiTableColumnFlags_WidthFixed, 118.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(7, static_cast<int>(route_quality_.feedback_trends.size()));
                for (int i = 0; i < count; ++i) {
                    const FeedbackTrendBucketInfo& bucket = route_quality_.feedback_trends[static_cast<size_t>(i)];
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(bucket.period_start.empty() ? "unknown" : bucket.period_start, 18), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(std::to_string(bucket.feedback_count));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(std::to_string(bucket.positive_count) + " (" + FormatPercent(bucket.positive_rate) + ")");
                    ImGui::TableSetColumnIndex(3);
                    TextColor(std::to_string(bucket.negative_count) + " (" + FormatPercent(bucket.negative_rate) + ")", bucket.negative_rate >= 0.30 ? Rgba(248, 113, 113) : Rgba(151, 160, 171));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(std::to_string(bucket.applied_count) + " / " + std::to_string(bucket.rolled_back_count));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(std::to_string(bucket.regenerated_count) + " / " + std::to_string(bucket.corrected_count));
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.feedback_events.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Recent Feedback Events");
            if (ImGui::BeginTable("route_quality_feedback_events_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Time", ImGuiTableColumnFlags_WidthFixed, 124.0f);
                ImGui::TableSetupColumn("Sentiment", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 108.0f);
                ImGui::TableSetupColumn("Target", ImGuiTableColumnFlags_WidthFixed, 120.0f);
                ImGui::TableSetupColumn("Model");
                ImGui::TableSetupColumn("Route", ImGuiTableColumnFlags_WidthFixed, 96.0f);
                ImGui::TableSetupColumn("Context");
                ImGui::TableHeadersRow();
                const int count = std::min(8, static_cast<int>(route_quality_.feedback_events.size()));
                for (int i = 0; i < count; ++i) {
                    const FeedbackTelemetryEntryInfo& event = route_quality_.feedback_events[static_cast<size_t>(i)];
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(Shorten(event.created_at.empty() ? "-" : event.created_at, 22));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(event.sentiment.empty() ? "neutral" : event.sentiment, 16), feedback_color(event.sentiment));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(event.action.empty() ? "manual" : event.action, 22));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(Shorten(event.target.empty() ? "assistant_response" : event.target, 24));
                    ImGui::TableSetColumnIndex(4);
                    TextColor(Shorten(event.model_label.empty() ? "-" : event.model_label, 30), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(Shorten(event.route_role.empty() ? "-" : event.route_role, 20));
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(event.context.empty() ? event.task_id : event.context, 48));
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.providers.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            if (ImGui::BeginTable("route_quality_providers_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Provider");
                ImGui::TableSetupColumn("Model");
                ImGui::TableSetupColumn("Success", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Fallback", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Cost", ImGuiTableColumnFlags_WidthFixed, 76.0f);
                ImGui::TableSetupColumn("Estimator", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(4, static_cast<int>(route_quality_.providers.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityProviderRollupInfo& provider = route_quality_.providers[static_cast<size_t>(i)];
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(provider.provider_label.empty() ? provider.provider_id : provider.provider_label, 28), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(provider.model.empty() ? "-" : provider.model, 30));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(FormatPercent(provider.success_rate));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(FormatPercent(provider.fallback_rate));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(FormatCostUsd(provider.estimated_cost_usd, provider.estimated_cost_usd > 0.0));
                    ImGui::TableSetColumnIndex(5);
                    const std::string estimator = provider.token_estimator_sources.empty() ? "-" : provider.token_estimator_sources.front();
                    TextMuted(Shorten(estimator, 24));
                }
                ImGui::EndTable();
            }
        }

        if (!route_quality_.roles.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            if (ImGui::BeginTable("route_quality_roles_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Role");
                ImGui::TableSetupColumn("Attempts", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Success", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Fallback", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Cost", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableHeadersRow();
                const int count = std::min(5, static_cast<int>(route_quality_.roles.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteQualityRoleRollupInfo& role = route_quality_.roles[static_cast<size_t>(i)];
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(role.role.empty() ? "unknown" : role.role, 36), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(std::to_string(role.attempts));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(FormatPercent(role.success_rate));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(std::to_string(role.fallback_attempts));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(FormatCostUsd(role.estimated_cost_usd, role.estimated_cost_usd > 0.0));
                }
                ImGui::EndTable();
            }
        }
    } else if (!route_quality_error_.empty()) {
        TextMuted("Route-quality rollup unavailable: " + Shorten(route_quality_error_, 128));
    } else {
        TextMuted("Route-quality rollups will appear after refresh when the backend supports them.");
    }

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    TextColor("Policy Diff", Rgba(246, 248, 251));
    if (route_policy_diff_loaded_) {
        const auto action_color = [](const std::string& action) {
            const std::string lowered = Lower(action);
            if (lowered == "promote" || lowered == "switch_primary") {
                return Rgba(38, 221, 123);
            }
            if (lowered == "deprioritize") {
                return Rgba(248, 113, 113);
            }
            if (lowered == "strengthen_fallback" || lowered == "rebalance" || lowered == "monitor") {
                return Rgba(205, 154, 82);
            }
            return Rgba(151, 160, 171);
        };
        const auto risk_color = [](const std::string& risk) {
            const std::string lowered = Lower(risk);
            if (lowered == "high") {
                return Rgba(248, 113, 113);
            }
            if (lowered == "medium") {
                return Rgba(205, 154, 82);
            }
            return Rgba(38, 221, 123);
        };

        const int provider_change_count = static_cast<int>(std::count_if(
            route_policy_diff_.provider_proposals.begin(),
            route_policy_diff_.provider_proposals.end(),
            [](const RoutePolicyProviderProposalInfo& proposal) {
                const std::string action = Lower(proposal.action);
                return action != "hold" && action != "monitor";
            }));
        const int role_change_count = static_cast<int>(std::count_if(
            route_policy_diff_.role_proposals.begin(),
            route_policy_diff_.role_proposals.end(),
            [](const RoutePolicyRoleProposalInfo& proposal) {
                return Lower(proposal.action) != "keep";
            }));

        ImGui::Columns(4, "route_policy_diff_summary", false);
        TextMuted("Source");
        TextColor(Shorten(route_policy_diff_.source.empty() ? "live" : route_policy_diff_.source, 18), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Providers");
        TextColor(std::to_string(provider_change_count) + " / " + std::to_string(route_policy_diff_.provider_proposals.size()), provider_change_count > 0 ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
        ImGui::NextColumn();
        TextMuted("Roles");
        TextColor(std::to_string(role_change_count) + " / " + std::to_string(route_policy_diff_.role_proposals.size()), role_change_count > 0 ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
        ImGui::NextColumn();
        TextMuted("Min Attempts");
        TextColor(std::to_string(route_policy_diff_.min_attempts), Rgba(246, 248, 251));
        ImGui::Columns(1);

        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        ImGui::BeginDisabled(busy_ || (provider_change_count + role_change_count) <= 0);
        if (IconTextButton("apply_safe_policy_diff", IconGlyph::Bolt, "Apply Safe Policy", ImVec2(158.0f, 32.0f), Rgba(20, 98, 62), Rgba(22, 130, 76), Rgba(246, 248, 251))) {
            pending_popup_ = "Aegis Policy Apply";
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        TextMuted((provider_change_count + role_change_count) > 0
            ? "Checkpointed registry update."
            : "No actionable updates.");

        if (!route_policy_diff_.recommendations.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            const int count = std::min(2, static_cast<int>(route_policy_diff_.recommendations.size()));
            for (int i = 0; i < count; ++i) {
                TextMuted(Shorten(route_policy_diff_.recommendations[static_cast<size_t>(i)], 136));
            }
        }
        if (!route_policy_diff_.warnings.empty()) {
            const int count = std::min(2, static_cast<int>(route_policy_diff_.warnings.size()));
            for (int i = 0; i < count; ++i) {
                TextColor(Shorten(route_policy_diff_.warnings[static_cast<size_t>(i)], 136), Rgba(205, 154, 82));
            }
        }

        if (!route_policy_diff_.provider_proposals.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Provider Proposals");
            if (ImGui::BeginTable("route_policy_provider_diff_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Provider / Model");
                ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 112.0f);
                ImGui::TableSetupColumn("Risk", ImGuiTableColumnFlags_WidthFixed, 72.0f);
                ImGui::TableSetupColumn("Rank", ImGuiTableColumnFlags_WidthFixed, 62.0f);
                ImGui::TableSetupColumn("Success", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Fallback", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Why");
                ImGui::TableHeadersRow();
                const int count = std::min(5, static_cast<int>(route_policy_diff_.provider_proposals.size()));
                for (int i = 0; i < count; ++i) {
                    const RoutePolicyProviderProposalInfo& proposal = route_policy_diff_.provider_proposals[static_cast<size_t>(i)];
                    const std::string provider = proposal.provider_label.empty() ? proposal.provider_id : proposal.provider_label;
                    const std::string provider_model = provider + (proposal.model.empty() ? "" : " / " + proposal.model);
                    const std::string reason = proposal.reasons.empty() ? JoinList(proposal.risks) : proposal.reasons.front();
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(provider_model.empty() ? "unknown" : provider_model, 42), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(proposal.action, 24), action_color(proposal.action));
                    ImGui::TableSetColumnIndex(2);
                    TextColor(Shorten(proposal.risk_level, 12), risk_color(proposal.risk_level));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(std::to_string(proposal.observed_rank) + ">" + std::to_string(proposal.proposed_rank));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(FormatPercent(proposal.success_rate, proposal.attempts > 0));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(FormatPercent(proposal.fallback_rate, proposal.attempts > 0));
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(reason.empty() ? "-" : reason, 72));
                }
                ImGui::EndTable();
            }
        }

        if (!route_policy_diff_.role_proposals.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("Role Proposals");
            if (ImGui::BeginTable("route_policy_role_diff_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 88.0f);
                ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Observed");
                ImGui::TableSetupColumn("Proposed");
                ImGui::TableSetupColumn("Success", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Why");
                ImGui::TableHeadersRow();
                const int count = std::min(5, static_cast<int>(route_policy_diff_.role_proposals.size()));
                for (int i = 0; i < count; ++i) {
                    const RoutePolicyRoleProposalInfo& proposal = route_policy_diff_.role_proposals[static_cast<size_t>(i)];
                    const std::string reason = proposal.reasons.empty() ? JoinList(proposal.risks) : proposal.reasons.front();
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(proposal.role.empty() ? "unknown" : proposal.role, 18), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(proposal.action, 28), action_color(proposal.action));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(proposal.observed_primary_provider.empty() ? "-" : proposal.observed_primary_provider, 34));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(Shorten(proposal.proposed_primary_provider.empty() ? "-" : proposal.proposed_primary_provider, 34));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(FormatPercent(proposal.success_rate, proposal.attempts > 0));
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(Shorten(reason.empty() ? "-" : reason, 72));
                }
                ImGui::EndTable();
            }
        }
    } else if (!route_policy_diff_error_.empty()) {
        TextMuted("Policy diff unavailable: " + Shorten(route_policy_diff_error_, 128));
    } else {
        TextMuted("Policy-diff proposals will appear after refresh when the backend supports them.");
    }

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    TextColor("Route Health", Rgba(246, 248, 251));
    if (route_health_loaded_) {
        int cooldown_count = 0;
        int penalized_count = 0;
        int terminal_count = 0;
        int failure_count = 0;
        for (const RouteHealthInfo& signal : route_health_) {
            if (signal.cooldown) {
                ++cooldown_count;
            }
            if (signal.penalty > 0.0) {
                ++penalized_count;
            }
            terminal_count += signal.terminal_attempts;
            failure_count += signal.failures;
        }
        const double weighted_failure_rate = terminal_count > 0
            ? static_cast<double>(failure_count) / static_cast<double>(terminal_count)
            : 0.0;

        ImGui::Columns(4, "route_health_summary", false);
        TextMuted("Signals");
        TextColor(std::to_string(route_health_.size()), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Penalized");
        TextColor(std::to_string(penalized_count), penalized_count > 0 ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
        ImGui::NextColumn();
        TextMuted("Cooldown");
        TextColor(std::to_string(cooldown_count), cooldown_count > 0 ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
        ImGui::NextColumn();
        TextMuted("Failure");
        TextColor(FormatPercent(weighted_failure_rate, terminal_count > 0), weighted_failure_rate >= 0.34 ? Rgba(205, 154, 82) : Rgba(246, 248, 251));
        ImGui::Columns(1);

        if (route_health_.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextMuted("No route-health signals have been recorded yet.");
        } else {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            if (ImGui::BeginTable("route_health_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 76.0f);
                ImGui::TableSetupColumn("Provider / Model");
                ImGui::TableSetupColumn("Terminal", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Success", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Failure", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Health", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Recommendation");
                ImGui::TableHeadersRow();
                const int count = std::min(8, static_cast<int>(route_health_.size()));
                for (int i = 0; i < count; ++i) {
                    const RouteHealthInfo& signal = route_health_[static_cast<size_t>(i)];
                    const std::string provider = signal.provider_label.empty() ? signal.provider_id : signal.provider_label;
                    const std::string provider_model = provider.empty()
                        ? signal.model
                        : provider + (signal.model.empty() ? "" : " / " + signal.model);
                    std::string health = "OK";
                    ImVec4 health_color = Rgba(38, 221, 123);
                    if (signal.cooldown) {
                        health = "Cooldown";
                        health_color = Rgba(248, 113, 113);
                    } else if (signal.penalty > 0.0) {
                        health = "-" + FormatNumber(signal.penalty, true, 0);
                        health_color = Rgba(205, 154, 82);
                    }

                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(Shorten(signal.role.empty() ? "unknown" : signal.role, 18));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(provider_model.empty() ? "unknown" : provider_model, 42), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(std::to_string(signal.terminal_attempts));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(FormatPercent(signal.success_rate, signal.terminal_attempts > 0));
                    ImGui::TableSetColumnIndex(4);
                    TextColor(FormatPercent(signal.failure_rate, signal.terminal_attempts > 0), signal.failure_rate >= 0.34 ? Rgba(205, 154, 82) : Rgba(151, 160, 171));
                    ImGui::TableSetColumnIndex(5);
                    TextColor(health, health_color);
                    ImGui::TableSetColumnIndex(6);
                    std::string recommendation = signal.recommendation.empty() ? signal.latest_error : signal.recommendation;
                    if (recommendation.empty() && signal.has_average_latency) {
                        recommendation = "Average latency " + FormatNumber(signal.average_latency_ms / 1000.0, true, 1) + "s.";
                    }
                    TextMuted(Shorten(recommendation.empty() ? "-" : recommendation, 62));
                }
                ImGui::EndTable();
            }
        }
    } else if (!route_health_error_.empty()) {
        TextMuted("Route-health signals unavailable: " + Shorten(route_health_error_, 128));
    } else {
        TextMuted("Route-health signals will appear after refresh when the backend supports them.");
    }

    const auto privacy_color = [](const std::string& privacy) {
        const std::string lowered = Lower(privacy);
        if (lowered.find("cloud") != std::string::npos || lowered.find("remote") != std::string::npos) {
            return Rgba(205, 154, 82);
        }
        if (lowered.find("local") != std::string::npos) {
            return Rgba(38, 221, 123);
        }
        return Rgba(151, 160, 171);
    };
    const auto status_color = [](const std::string& status) {
        const std::string lowered = Lower(status);
        if (lowered == "succeeded") {
            return Rgba(38, 221, 123);
        }
        if (lowered == "failed" || lowered == "canceled") {
            return Rgba(248, 113, 113);
        }
        if (lowered == "running" || lowered == "fallback") {
            return Rgba(205, 154, 82);
        }
        return Rgba(151, 160, 171);
    };

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    TextColor("Fallback Inspector", Rgba(246, 248, 251));
    if (fallback_inspector_loaded_) {
        int candidate_count = 0;
        int unresolved_count = 0;
        int fallback_role_count = 0;
        int planned_only_count = 0;
        for (const FallbackInspectorTaskInfo& task : fallback_inspector_.tasks) {
            candidate_count += static_cast<int>(task.candidates.size());
            fallback_role_count += static_cast<int>(task.fallback_roles.size());
            for (const FallbackInspectorCandidateInfo& candidate : task.candidates) {
                if (candidate.has_registry_resolved && !candidate.registry_resolved) {
                    ++unresolved_count;
                }
            }
            if (!task.attempts.empty()) {
                bool all_planned = true;
                for (const ModelAttemptTelemetryEntryInfo& entry : task.attempts) {
                    const std::string lowered = Lower(entry.attempt.status);
                    if (lowered != "planned" && lowered != "running" && lowered != "skipped") {
                        all_planned = false;
                        break;
                    }
                }
                if (all_planned) {
                    ++planned_only_count;
                }
            }
        }

        ImGui::Columns(4, "fallback_inspector_summary", false);
        TextMuted("Tasks");
        TextColor(std::to_string(fallback_inspector_.tasks.size()), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Candidates");
        TextColor(std::to_string(candidate_count), Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Fallback Roles");
        TextColor(std::to_string(fallback_role_count), fallback_role_count > 0 ? Rgba(205, 154, 82) : Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Unresolved");
        TextColor(std::to_string(unresolved_count), unresolved_count > 0 ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
        ImGui::Columns(1);

        if (!fallback_inspector_.recommendations.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextMuted("Recommendations");
            const int recommendation_count = static_cast<int>(fallback_inspector_.recommendations.size());
            for (int i = 0; i < recommendation_count; ++i) {
                TextMuted(Shorten(fallback_inspector_.recommendations[static_cast<size_t>(i)], 136));
            }
        } else if (planned_only_count > 0) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextMuted(std::to_string(planned_only_count) + " task(s) are still planned-only; live routed execution will make this view more useful.");
        }

        if (fallback_inspector_.tasks.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted("No inspected fallback tasks have been recorded yet.");
        } else {
            selected_fallback_inspector_task_index_ = std::clamp(
                selected_fallback_inspector_task_index_ < 0 ? 0 : selected_fallback_inspector_task_index_,
                0,
                static_cast<int>(fallback_inspector_.tasks.size()) - 1);

            const auto task_route = [](const FallbackInspectorTaskInfo& task) {
                if (task.has_task_plan && task.task_plan.has_routing) {
                    return task.task_plan.routing.task_role + " / " + task.task_plan.routing.privacy_mode;
                }
                if (task.has_task_plan) {
                    return task.task_plan.intent.empty() ? std::string("planned") : task.task_plan.intent;
                }
                return std::string("unplanned");
            };
            const auto task_state = [](const FallbackInspectorTaskInfo& task) {
                if (!task.fallback_roles.empty()) {
                    return std::string("fallback");
                }
                if (!task.attempts.empty()) {
                    bool all_planned = true;
                    for (const ModelAttemptTelemetryEntryInfo& entry : task.attempts) {
                        const std::string lowered = Lower(entry.attempt.status);
                        if (lowered != "planned" && lowered != "running" && lowered != "skipped") {
                            all_planned = false;
                            break;
                        }
                    }
                    if (all_planned) {
                        return std::string("planned-only");
                    }
                }
                return task.status.empty() ? std::string("unknown") : task.status;
            };

            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            if (ImGui::BeginTable("fallback_task_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Task");
                ImGui::TableSetupColumn("Route");
                ImGui::TableSetupColumn("Candidates", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Attempts", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("State", ImGuiTableColumnFlags_WidthFixed, 98.0f);
                ImGui::TableHeadersRow();
                for (int i = 0; i < static_cast<int>(fallback_inspector_.tasks.size()); ++i) {
                    const FallbackInspectorTaskInfo& task = fallback_inspector_.tasks[static_cast<size_t>(i)];
                    const bool selected = selected_fallback_inspector_task_index_ == i;
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    const std::string task_label = Shorten(task.message.empty() ? task.task_id : task.message, 48) + "##fallback_task_" + std::to_string(i);
                    if (ImGui::Selectable(task_label.c_str(), selected, ImGuiSelectableFlags_SpanAllColumns)) {
                        selected_fallback_inspector_task_index_ = i;
                    }
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(task_route(task), 36));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(std::to_string(task.candidates.size()));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(std::to_string(task.attempts.size()));
                    ImGui::TableSetColumnIndex(4);
                    const std::string state = task_state(task);
                    TextColor(Shorten(state, 18), status_color(state));
                }
                ImGui::EndTable();
            }

            const FallbackInspectorTaskInfo& selected_task =
                fallback_inspector_.tasks[static_cast<size_t>(selected_fallback_inspector_task_index_)];
            ImGui::Dummy(ImVec2(0.0f, 10.0f));
            TextColor("Selected Route", Rgba(246, 248, 251));
            TextColor(Shorten(task_route(selected_task) + " - " + selected_task.message, 150), Rgba(246, 248, 251));
            TextMuted(Shorten(selected_task.summary.empty() ? selected_task.task_id : selected_task.summary, 170));
            TextMuted("Task: " + Shorten(selected_task.task_id.empty() ? "unknown" : selected_task.task_id, 42) +
                " | Status: " + (selected_task.status.empty() ? "unknown" : selected_task.status) +
                " | Created: " + Shorten(selected_task.created_at.empty() ? "-" : selected_task.created_at, 22));
            if (selected_task.has_context_budget) {
                TextMuted("Context budget: " +
                    std::to_string(selected_task.context_budget.estimated_context_tokens) + "/" +
                    std::to_string(selected_task.context_budget.max_context_tokens) +
                    " tokens, files " + std::to_string(selected_task.context_budget.selected_file_count) +
                    " selected / " + std::to_string(selected_task.context_budget.omitted_file_count) + " omitted.");
            }
            if (!selected_task.fallback_roles.empty()) {
                TextMuted("Fallback roles: " + Shorten(JoinList(selected_task.fallback_roles), 140));
            }
            if (!selected_task.recommendations.empty()) {
                ImGui::Dummy(ImVec2(0.0f, 6.0f));
                TextMuted("Task recommendations");
                for (const std::string& recommendation : selected_task.recommendations) {
                    TextMuted(Shorten(recommendation, 160));
                }
            }

            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Candidate Drilldown", Rgba(246, 248, 251));
            if (selected_task.candidates.empty()) {
                TextMuted("No route candidates were recorded for this task.");
            } else if (ImGui::BeginTable("fallback_candidate_drilldown_table", 9, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Candidate");
                ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Provider / Model");
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Registry", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 84.0f);
                ImGui::TableSetupColumn("Cost", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Context", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Metadata");
                ImGui::TableHeadersRow();
                for (const FallbackInspectorCandidateInfo& candidate : selected_task.candidates) {
                    const std::string provider = candidate.provider_label.empty()
                        ? (candidate.provider_id.empty() ? candidate.provider_hint : candidate.provider_id)
                        : candidate.provider_label;
                    const std::string provider_model = provider.empty()
                        ? candidate.model
                        : provider + (candidate.model.empty() ? "" : " / " + candidate.model);
                    const std::string registry = candidate.has_registry_resolved
                        ? (candidate.registry_resolved ? "resolved" : "missing")
                        : "-";
                    const ImVec4 registry_color = candidate.has_registry_resolved && !candidate.registry_resolved
                        ? Rgba(248, 113, 113)
                        : Rgba(151, 160, 171);
                    const std::string candidate_label = candidate.candidate_id.empty()
                        ? std::to_string(candidate.index) + ". " + candidate.role
                        : candidate.candidate_id;
                    const std::string token_text =
                        FormatOptionalInt(candidate.input_tokens, candidate.has_input_tokens) + "/" +
                        FormatOptionalInt(candidate.output_tokens, candidate.has_output_tokens);
                    const std::string context_text = candidate.has_context_window_utilization
                        ? FormatPercent(candidate.context_window_utilization)
                        : (candidate.has_context_window ? std::to_string(candidate.context_window) : "-");
                    std::string metadata = candidate.token_estimator_source.empty() ? "" : candidate.token_estimator_source;
                    if (!candidate.reason.empty()) {
                        metadata += metadata.empty() ? candidate.reason : " | " + candidate.reason;
                    }
                    if (!candidate.error.empty()) {
                        metadata += metadata.empty() ? candidate.error : " | " + candidate.error;
                    }

                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextColor(Shorten(candidate_label, 30), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(Shorten(candidate.role.empty() ? "-" : candidate.role, 20));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(provider_model.empty() ? "-" : provider_model, 38));
                    ImGui::TableSetColumnIndex(3);
                    TextColor(candidate.status, status_color(candidate.status));
                    ImGui::TableSetColumnIndex(4);
                    TextColor(registry, registry_color);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(token_text);
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(FormatCostUsd(candidate.estimated_cost_usd, candidate.has_estimated_cost));
                    ImGui::TableSetColumnIndex(7);
                    TextMuted(context_text);
                    ImGui::TableSetColumnIndex(8);
                    TextMuted(Shorten(metadata.empty() ? "-" : metadata, 72));
                }
                ImGui::EndTable();
            }

            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Attempt Drilldown", Rgba(246, 248, 251));
            if (selected_task.attempts.empty()) {
                TextMuted("No execution attempts were recorded for this task.");
            } else if (ImGui::BeginTable("fallback_attempt_drilldown_table", 9, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Try", ImGuiTableColumnFlags_WidthFixed, 42.0f);
                ImGui::TableSetupColumn("Candidate");
                ImGui::TableSetupColumn("Provider / Model");
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 84.0f);
                ImGui::TableSetupColumn("Cost", ImGuiTableColumnFlags_WidthFixed, 74.0f);
                ImGui::TableSetupColumn("Latency", ImGuiTableColumnFlags_WidthFixed, 72.0f);
                ImGui::TableSetupColumn("Context", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Metadata");
                ImGui::TableHeadersRow();
                int attempt_index = 0;
                for (const ModelAttemptTelemetryEntryInfo& entry : selected_task.attempts) {
                    const ModelAttemptInfo& attempt = entry.attempt;
                    const std::string provider = attempt.provider_label.empty() ? attempt.provider_id : attempt.provider_label;
                    const std::string provider_model = provider.empty()
                        ? attempt.model
                        : provider + (attempt.model.empty() ? "" : " / " + attempt.model);
                    std::string candidate_label = attempt.candidate_id.empty()
                        ? (attempt.role.empty() ? "-" : attempt.role)
                        : attempt.candidate_id;
                    if (!attempt.candidate_source.empty()) {
                        candidate_label += " (" + attempt.candidate_source + ")";
                    }
                    const std::string token_text =
                        FormatOptionalInt(attempt.input_tokens, attempt.has_input_tokens) + "/" +
                        FormatOptionalInt(attempt.output_tokens, attempt.has_output_tokens);
                    const std::string latency_text = attempt.has_latency ? std::to_string(attempt.latency_ms) + " ms" : "-";
                    const std::string context_text = attempt.has_context_window_utilization
                        ? FormatPercent(attempt.context_window_utilization)
                        : (attempt.has_context_window ? std::to_string(attempt.context_window) : "-");
                    std::string metadata = attempt.token_estimator_source;
                    const std::string attempt_profile = attempt.route_profile.label.empty()
                        ? attempt.route_profile.id
                        : attempt.route_profile.label;
                    if (!attempt_profile.empty()) {
                        metadata += metadata.empty() ? ("profile " + attempt_profile) : " | profile " + attempt_profile;
                    }
                    if (attempt.has_benchmark_suite_score) {
                        const std::string suite = attempt.benchmark_suite.empty() ? "route" : attempt.benchmark_suite;
                        const std::string benchmark = suite + " bench " + FormatPercent(attempt.benchmark_suite_score);
                        metadata += metadata.empty() ? benchmark : " | " + benchmark;
                    }
                    if (!attempt.candidate_provider_hint.empty()) {
                        metadata += metadata.empty() ? attempt.candidate_provider_hint : " | hint: " + attempt.candidate_provider_hint;
                    }
                    if (attempt.structured_preview_emitted) {
                        std::string preview = "preview " + std::to_string(attempt.structured_preview_delta_count) +
                            " delta(s), " + std::to_string(attempt.structured_preview_char_count) + " chars";
                        if (attempt.structured_preview_final_winner) {
                            preview += ", final winner";
                        }
                        if (attempt.structured_preview_retired) {
                            preview += ", reset";
                            if (!attempt.structured_preview_retired_reason.empty()) {
                                preview += " (" + attempt.structured_preview_retired_reason + ")";
                            }
                        }
                        metadata += metadata.empty() ? preview : " | " + preview;
                    }
                    if (!attempt.reason.empty()) {
                        metadata += metadata.empty() ? attempt.reason : " | " + attempt.reason;
                    }
                    if (!attempt.error.empty()) {
                        metadata += metadata.empty() ? attempt.error : " | " + attempt.error;
                    }

                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(std::to_string(attempt.attempt > 0 ? attempt.attempt : attempt_index + 1));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(candidate_label, 34), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(provider_model.empty() ? "-" : provider_model, 38));
                    ImGui::TableSetColumnIndex(3);
                    TextColor(attempt.status, status_color(attempt.status));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(token_text);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(FormatCostUsd(attempt.estimated_cost_usd, attempt.has_estimated_cost));
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(latency_text);
                    ImGui::TableSetColumnIndex(7);
                    TextMuted(context_text);
                    ImGui::TableSetColumnIndex(8);
                    TextMuted(Shorten(metadata.empty() ? "-" : metadata, 72));
                    ++attempt_index;
                }
                ImGui::EndTable();
            }
        }
    } else if (!fallback_inspector_error_.empty()) {
        TextMuted("Fallback inspector unavailable: " + Shorten(fallback_inspector_error_, 128));
    } else {
        TextMuted("Fallback inspection will appear after refresh when the backend supports it.");
    }

    ImGui::Dummy(ImVec2(0.0f, 14.0f));
    TextColor("Context Budgets", Rgba(246, 248, 251));
    if (telemetry_.context_budgets.empty()) {
        TextMuted("No context budget telemetry has been recorded yet.");
    } else if (ImGui::BeginTable("planning_budget_table", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Created", ImGuiTableColumnFlags_WidthFixed, 128.0f);
        ImGui::TableSetupColumn("Task", ImGuiTableColumnFlags_WidthFixed, 108.0f);
        ImGui::TableSetupColumn("Route");
        ImGui::TableSetupColumn("Strategy", ImGuiTableColumnFlags_WidthFixed, 112.0f);
        ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 118.0f);
        ImGui::TableSetupColumn("Files", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Privacy", ImGuiTableColumnFlags_WidthFixed, 94.0f);
        ImGui::TableHeadersRow();
        const int count = std::min(12, static_cast<int>(telemetry_.context_budgets.size()));
        for (int i = 0; i < count; ++i) {
            const ContextBudgetTelemetryEntryInfo& entry = telemetry_.context_budgets[static_cast<size_t>(i)];
            const ContextBudgetInfo& budget = entry.payload;
            const std::string role = !budget.route_role.empty() ? budget.route_role : (!entry.route_role.empty() ? entry.route_role : entry.intent);
            const std::string strategy = !budget.strategy.empty() ? budget.strategy : entry.strategy;
            const int max_tokens = budget.max_context_tokens > 0 ? budget.max_context_tokens : entry.max_context_tokens;
            const int estimated_tokens = budget.estimated_context_tokens > 0 ? budget.estimated_context_tokens : entry.estimated_context_tokens;
            const int reserve_tokens = budget.reserve_response_tokens > 0 ? budget.reserve_response_tokens : entry.reserve_response_tokens;
            const int selected_files = budget.selected_file_count > 0 ? budget.selected_file_count : entry.selected_file_count;
            const int omitted_files = budget.omitted_file_count > 0 ? budget.omitted_file_count : entry.omitted_file_count;
            const std::string privacy = !budget.privacy_mode.empty() ? budget.privacy_mode : entry.privacy_mode;

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(CompactTimestamp(entry.created_at));
            ImGui::TableSetColumnIndex(1);
            TextMuted(Shorten(entry.task_id, 12));
            ImGui::TableSetColumnIndex(2);
            TextColor(Shorten(role.empty() ? "general" : role, 42), Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(3);
            TextMuted(Shorten(strategy.empty() ? "-" : strategy, 18));
            ImGui::TableSetColumnIndex(4);
            TextMuted(std::to_string(estimated_tokens + reserve_tokens) + " / " + (max_tokens > 0 ? std::to_string(max_tokens) : std::string("-")));
            ImGui::TableSetColumnIndex(5);
            TextMuted(std::to_string(selected_files) + " / " + std::to_string(omitted_files));
            ImGui::TableSetColumnIndex(6);
            Pill(Shorten(privacy, 14).c_str(), privacy_color(privacy));
        }
        ImGui::EndTable();
        if (telemetry_.context_budgets.size() > 12) {
            TextMuted("Showing 12 of " + std::to_string(telemetry_.context_budgets.size()) + " context budget entries.");
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 16.0f));
    TextColor("Model Attempts", Rgba(246, 248, 251));
    if (telemetry_.model_attempts.empty()) {
        TextMuted("No model attempt telemetry has been recorded yet.");
    } else if (ImGui::BeginTable("planning_attempt_table", 8, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Created", ImGuiTableColumnFlags_WidthFixed, 128.0f);
        ImGui::TableSetupColumn("Task", ImGuiTableColumnFlags_WidthFixed, 108.0f);
        ImGui::TableSetupColumn("Try", ImGuiTableColumnFlags_WidthFixed, 42.0f);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 86.0f);
        ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 130.0f);
        ImGui::TableSetupColumn("Model");
        ImGui::TableSetupColumn("Tokens", ImGuiTableColumnFlags_WidthFixed, 92.0f);
        ImGui::TableSetupColumn("Cost", ImGuiTableColumnFlags_WidthFixed, 76.0f);
        ImGui::TableHeadersRow();
        const int count = std::min(24, static_cast<int>(telemetry_.model_attempts.size()));
        for (int i = 0; i < count; ++i) {
            const ModelAttemptTelemetryEntryInfo& entry = telemetry_.model_attempts[static_cast<size_t>(i)];
            const ModelAttemptInfo& attempt = entry.attempt;
            const std::string provider = attempt.provider_label.empty() ? attempt.provider_id : attempt.provider_label;
            const std::string token_text = FormatOptionalInt(attempt.input_tokens, attempt.has_input_tokens) + " / " +
                FormatOptionalInt(attempt.output_tokens, attempt.has_output_tokens);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(CompactTimestamp(entry.created_at));
            ImGui::TableSetColumnIndex(1);
            TextMuted(Shorten(entry.task_id, 12));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(attempt.attempt > 0 ? attempt.attempt : i + 1));
            ImGui::TableSetColumnIndex(3);
            Pill(Shorten(attempt.status.empty() ? "planned" : attempt.status, 12).c_str(), status_color(attempt.status));
            ImGui::TableSetColumnIndex(4);
            TextMuted(Shorten(provider.empty() ? attempt.provider_api : provider, 22));
            ImGui::TableSetColumnIndex(5);
            TextColor(Shorten(attempt.model.empty() ? attempt.role : attempt.model, 44), Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(6);
            TextMuted(token_text);
            ImGui::TableSetColumnIndex(7);
            TextMuted(FormatCostUsd(attempt.estimated_cost_usd, attempt.has_estimated_cost));
        }
        ImGui::EndTable();
        if (telemetry_.model_attempts.size() > 24) {
            TextMuted("Showing 24 of " + std::to_string(telemetry_.model_attempts.size()) + " model attempt entries.");
        }
    }
}

void AegisChatApp::RenderPolicyApplyConfirmModal()
{
    const auto provider_actionable = [](const RoutePolicyProviderProposalInfo& proposal) {
        const std::string action = Lower(proposal.action);
        return (action == "promote" || action == "deprioritize") &&
            proposal.confidence >= 0.55 &&
            Lower(proposal.risk_level) != "high";
    };
    const auto role_actionable = [](const RoutePolicyRoleProposalInfo& proposal) {
        const std::string action = Lower(proposal.action);
        if (action != "switch_primary" && action != "strengthen_fallback" && action != "rebalance") {
            return false;
        }
        if (proposal.confidence < 0.55) {
            return false;
        }
        for (const std::string& risk : proposal.risks) {
            const std::string lowered = Lower(risk);
            if (lowered.find("only one provider") != std::string::npos ||
                lowered.find("insufficient") != std::string::npos ||
                lowered.find("below") != std::string::npos) {
                return false;
            }
        }
        return true;
    };
    const auto action_color = [](const std::string& action) {
        const std::string lowered = Lower(action);
        if (lowered == "promote" || lowered == "switch_primary") {
            return Rgba(38, 221, 123);
        }
        if (lowered == "deprioritize") {
            return Rgba(248, 113, 113);
        }
        return Rgba(205, 154, 82);
    };

    const int provider_apply_count = static_cast<int>(std::count_if(
        route_policy_diff_.provider_proposals.begin(),
        route_policy_diff_.provider_proposals.end(),
        provider_actionable));
    const int role_apply_count = static_cast<int>(std::count_if(
        route_policy_diff_.role_proposals.begin(),
        route_policy_diff_.role_proposals.end(),
        role_actionable));
    const int total_apply_count = provider_apply_count + role_apply_count;

    TextColor("Apply Safe Policy", Rgba(246, 248, 251));
    TextMuted("This updates model routing only for confident, non-high-risk policy proposals. A registry checkpoint is created before changes are written.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    ImGui::Columns(4, "policy_apply_summary", false);
    TextMuted("Providers");
    TextColor(std::to_string(provider_apply_count) + " actionable", provider_apply_count > 0 ? Rgba(205, 154, 82) : Rgba(151, 160, 171));
    ImGui::NextColumn();
    TextMuted("Roles");
    TextColor(std::to_string(role_apply_count) + " actionable", role_apply_count > 0 ? Rgba(205, 154, 82) : Rgba(151, 160, 171));
    ImGui::NextColumn();
    TextMuted("Confidence");
    TextColor("55% minimum", Rgba(246, 248, 251));
    ImGui::NextColumn();
    TextMuted("Source");
    TextColor(Shorten(route_policy_diff_.source.empty() ? "live" : route_policy_diff_.source, 18), Rgba(246, 248, 251));
    ImGui::Columns(1);

    if (total_apply_count <= 0) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextColor("No policy proposal currently passes the safe-apply gate.", Rgba(205, 154, 82));
        TextMuted("Refresh Planning History after more routed tasks or feedback, then review the diff again.");
    }

    if (provider_apply_count > 0) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextMuted("Provider updates");
        if (ImGui::BeginTable("policy_apply_provider_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Provider");
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 112.0f);
            ImGui::TableSetupColumn("Risk", ImGuiTableColumnFlags_WidthFixed, 72.0f);
            ImGui::TableSetupColumn("Confidence", ImGuiTableColumnFlags_WidthFixed, 86.0f);
            ImGui::TableSetupColumn("Why");
            ImGui::TableHeadersRow();
            int shown = 0;
            for (const RoutePolicyProviderProposalInfo& proposal : route_policy_diff_.provider_proposals) {
                if (!provider_actionable(proposal) || shown >= 5) {
                    continue;
                }
                const std::string provider = proposal.provider_label.empty() ? proposal.provider_id : proposal.provider_label;
                const std::string reason = proposal.reasons.empty() ? JoinList(proposal.risks) : proposal.reasons.front();
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(Shorten(provider.empty() ? proposal.model : provider, 34), Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                TextColor(Shorten(proposal.action, 22), action_color(proposal.action));
                ImGui::TableSetColumnIndex(2);
                TextMuted(proposal.risk_level.empty() ? "low" : proposal.risk_level);
                ImGui::TableSetColumnIndex(3);
                TextMuted(FormatPercent(proposal.confidence));
                ImGui::TableSetColumnIndex(4);
                TextMuted(Shorten(reason.empty() ? "-" : reason, 68));
                ++shown;
            }
            ImGui::EndTable();
        }
    }

    if (role_apply_count > 0) {
        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        TextMuted("Role updates");
        if (ImGui::BeginTable("policy_apply_role_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 88.0f);
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 132.0f);
            ImGui::TableSetupColumn("Proposed");
            ImGui::TableSetupColumn("Confidence", ImGuiTableColumnFlags_WidthFixed, 86.0f);
            ImGui::TableSetupColumn("Why");
            ImGui::TableHeadersRow();
            int shown = 0;
            for (const RoutePolicyRoleProposalInfo& proposal : route_policy_diff_.role_proposals) {
                if (!role_actionable(proposal) || shown >= 5) {
                    continue;
                }
                const std::string reason = proposal.reasons.empty() ? JoinList(proposal.risks) : proposal.reasons.front();
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(Shorten(proposal.role.empty() ? "unknown" : proposal.role, 18), Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                TextColor(Shorten(proposal.action, 28), action_color(proposal.action));
                ImGui::TableSetColumnIndex(2);
                TextMuted(Shorten(proposal.proposed_primary_provider.empty() ? "-" : proposal.proposed_primary_provider, 36));
                ImGui::TableSetColumnIndex(3);
                TextMuted(FormatPercent(proposal.confidence));
                ImGui::TableSetColumnIndex(4);
                TextMuted(Shorten(reason.empty() ? "-" : reason, 68));
                ++shown;
            }
            ImGui::EndTable();
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 12.0f));
    ImGui::BeginDisabled(busy_ || total_apply_count <= 0);
    if (ImGui::Button("Confirm Apply", ImVec2(180.0f, 36.0f))) {
        ApplyRoutePolicyDiffToRoutes();
        ImGui::CloseCurrentPopup();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    if (ImGui::Button("Cancel", ImVec2(120.0f, 36.0f))) {
        ImGui::CloseCurrentPopup();
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Preview", ImVec2(150.0f, 36.0f))) {
        RefreshTelemetry();
        ImGui::CloseCurrentPopup();
    }
    ImGui::EndDisabled();
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
        RecordFeedback("liked", change_payload, "code_change; task_id=" + last_response_.task_id, "change_feedback", "code_change", last_response_.engine);
    }
    ImGui::SameLine();
    if (ImGui::Button("Reject Change")) {
        RecordFeedback("disliked", change_payload, "code_change; task_id=" + last_response_.task_id, "change_feedback", "code_change", last_response_.engine);
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
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_ || active_workspace.empty());
    if (ImGui::Button("Refresh Profile")) {
        RefreshWorkspaceProfile();
    }
    ImGui::EndDisabled();

    if (has_workspace_profile_snapshot_) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Workspace Profile", Rgba(246, 248, 251));
        const WorkspaceReadinessInfo& readiness = workspace_profile_.readiness;
        if (!readiness.status.empty() || !readiness.summary.empty() || !readiness.next_action.empty()) {
            const std::string readiness_status = readiness.status.empty() ? "unconfigured" : readiness.status;
            const std::string readiness_status_lower = Lower(readiness_status);
            const ImVec4 readiness_color =
                readiness_status_lower == "ready"
                    ? Rgba(38, 221, 123)
                    : (readiness_status_lower == "needs_repair"
                        ? Rgba(248, 64, 82)
                        : (readiness_status_lower == "needs_validation"
                            ? Rgba(205, 154, 82)
                            : Rgba(111, 180, 255)));
            Pill(Shorten(readiness_status, 22).c_str(), readiness_color);
            ImGui::SameLine();
            TextMuted("Readiness " + std::to_string(std::max(0, std::min(100, readiness.score))) + "%");

            if (ImGui::BeginTable("workspace_readiness_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Signal", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::string& value) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(value.empty() ? "-" : Shorten(value, 128));
                };
                row("Summary", readiness.summary);
                row("Next", readiness.next_action);
                row("Blockers", JoinList(readiness.blockers, " / "));
                row("Signals", JoinList(readiness.signals, " / "));
                ImGui::EndTable();
            }

            ImGui::BeginDisabled(readiness.next_action.empty() || busy_);
            if (ImGui::Button("Use Readiness Action")) {
                SetBuffer(message_buffer_, readiness.next_action);
                mode_ = readiness_status_lower == "needs_repair" ? "develop" : "review";
                active_nav_ = "chat";
                status_ = "Loaded workspace readiness action into the composer.";
            }
            ImGui::EndDisabled();
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
        }

        if (has_workspace_autopilot_status_snapshot_) {
            const WorkspaceAutopilotStatusInfo& autopilot = workspace_autopilot_status_;
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Autopilot Status", Rgba(246, 248, 251));
            const std::string phase = autopilot.phase.empty() ? "unconfigured" : autopilot.phase;
            const std::string phase_lower = Lower(phase);
            const ImVec4 phase_color =
                phase_lower == "ready"
                    ? Rgba(38, 221, 123)
                    : (phase_lower == "repair"
                        ? Rgba(248, 64, 82)
                        : (phase_lower == "validate" ? Rgba(205, 154, 82) : Rgba(111, 180, 255)));
            Pill(Shorten(phase, 22).c_str(), phase_color);
            ImGui::SameLine();
            TextMuted(
                std::string(autopilot.should_continue ? "Continue" : "Stop") +
                " / " + std::to_string(std::max(0, autopilot.pass_budget)) + " pass budget");

            if (ImGui::BeginTable("workspace_autopilot_status_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Signal", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::string& value) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(value.empty() ? "-" : Shorten(value, 128));
                };
                row("Mode", autopilot.recommended_mode);
                row("Next", autopilot.next_action);
                row("Validate", autopilot.validation_command);
                row("Latest", autopilot.latest_validation_status);
                row("Failed Step", autopilot.failed_step);
                row("Failed Command", autopilot.failed_step_command);
                row("First Diagnostic", autopilot.first_diagnostic);
                row("Repair Brief", autopilot.repair_brief);
                row("Stop Reason", autopilot.stop_reason);
                ImGui::EndTable();
            }

            if (!autopilot.next_open_items.empty()) {
                ImGui::Dummy(ImVec2(0.0f, 6.0f));
                TextMuted("Next queued work");
                const int item_count = std::min<int>(static_cast<int>(autopilot.next_open_items.size()), 5);
                for (int i = 0; i < item_count; ++i) {
                    ImGui::BulletText("%s", Shorten(autopilot.next_open_items[static_cast<size_t>(i)], 132).c_str());
                }
            }
            if (!autopilot.instruction_files.empty()) {
                std::string sources;
                const int source_count = std::min<int>(static_cast<int>(autopilot.instruction_files.size()), 4);
                for (int i = 0; i < source_count; ++i) {
                    const std::string& path = autopilot.instruction_files[static_cast<size_t>(i)].path;
                    if (path.empty()) {
                        continue;
                    }
                    if (!sources.empty()) {
                        sources += " / ";
                    }
                    sources += path;
                }
                if (!sources.empty()) {
                    TextMuted("Instruction files: " + Shorten(sources, 132));
                }
            }
            if (!autopilot.instruction_source.empty()) {
                TextMuted("Instruction source: " + Shorten(autopilot.instruction_source, 132));
            }

            ImGui::BeginDisabled(!autopilot.should_continue || Trim(autopilot.suggested_prompt).empty() || busy_);
            if (ImGui::Button("Use Autopilot Next Action")) {
                SetBuffer(message_buffer_, autopilot.suggested_prompt);
                mode_ = autopilot.recommended_mode.empty() ? mode_ : autopilot.recommended_mode;
                run_validation_ = autopilot.run_validation || run_validation_;
                max_repairs_ = std::max(max_repairs_, autopilot.max_repair_attempts);
                if (!autopilot.validation_command.empty()) {
                    SetBuffer(validation_command_buffer_, autopilot.validation_command);
                    SetBuffer(validation_label_buffer_, "Workspace autopilot validation");
                    SetBuffer(validation_notes_buffer_, "Loaded from backend workspace autopilot status.");
                }
                active_nav_ = "chat";
                status_ = "Loaded backend autopilot next action into the composer.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(autopilot.suggested_prompt.empty());
            if (ImGui::Button("Copy Autopilot Prompt")) {
                ImGui::SetClipboardText(autopilot.suggested_prompt.c_str());
                status_ = "Copied backend autopilot prompt.";
            }
            ImGui::EndDisabled();
        } else if (!workspace_autopilot_status_error_.empty()) {
            TextMuted("Autopilot status unavailable: " + Shorten(workspace_autopilot_status_error_, 128));
        }

        if (workspace_profile_.has_manifest) {
            const WorkspaceProjectManifestInfo& manifest = workspace_profile_.manifest;
            const std::string project_title = manifest.title.empty() ? manifest.project_name : manifest.title;
            Pill("Aegis manifest", Rgba(38, 221, 123));
            ImGui::SameLine();
            TextMuted(Shorten(project_title.empty() ? "Unnamed project" : project_title, 84));

            if (ImGui::BeginTable("workspace_profile_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Field", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::string& value) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(value.empty() ? "-" : Shorten(value, 112));
                };
                row("Preset", manifest.preset_label.empty() ? manifest.preset_id : manifest.preset_label);
                row("Stack", (manifest.framework.empty() ? "-" : manifest.framework) + " / " + (manifest.language.empty() ? "-" : manifest.language));
                row("Package", manifest.package_manager);
                row("Install", manifest.install_command);
                row("Validate", manifest.validation_command);
                row("Tags", JoinPalette(manifest.tags));
                row("Schema", manifest.schema);
                ImGui::EndTable();
            }

            ImGui::BeginDisabled(manifest.install_command.empty());
            if (ImGui::Button("Copy Install")) {
                ImGui::SetClipboardText(manifest.install_command.c_str());
                status_ = "Copied install command.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(manifest.validation_command.empty());
            if (ImGui::Button("Copy Validate")) {
                ImGui::SetClipboardText(manifest.validation_command.c_str());
                status_ = "Copied validation command.";
            }
            ImGui::EndDisabled();

            if (!manifest.handoff_goal.empty()) {
                TextMuted("Goal: " + Shorten(manifest.handoff_goal, 128));
            }
            if (!manifest.first_pass.empty() && ImGui::TreeNodeEx("First Pass", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (const std::string& step : manifest.first_pass) {
                    ImGui::BulletText("%s", Shorten(step, 128).c_str());
                }
                ImGui::TreePop();
            }
            if (!manifest.safety.empty() && ImGui::TreeNode("Safety Notes")) {
                for (const std::string& note : manifest.safety) {
                    ImGui::BulletText("%s", Shorten(note, 128).c_str());
                }
                ImGui::TreePop();
            }
        } else {
            TextMuted("No .aegis/project.json manifest found.");
            if (!workspace_profile_.recommendations.empty()) {
                TextMuted(Shorten(workspace_profile_.recommendations.front(), 128));
            }
        }

        if (workspace_profile_.has_instruction_status) {
            const WorkspaceInstructionStatusInfo& instruction = workspace_profile_.instruction_status;
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Instruction Checkpoint", Rgba(246, 248, 251));
            Pill(instruction.open_items > 0 ? "Open work" : "Tracked", instruction.open_items > 0 ? Rgba(248, 64, 82) : Rgba(38, 221, 123));
            ImGui::SameLine();
            TextMuted(
                std::to_string(instruction.open_items) + " open / " +
                std::to_string(instruction.completed_items) + " done / " +
                std::to_string(instruction.total_items) + " tracked");

            if (ImGui::BeginTable("workspace_instruction_checkpoint_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Signal", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::string& value) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(value.empty() ? "-" : Shorten(value, 128));
                };
                row("Updated", instruction.updated_at);
                row("Validation", instruction.validation_status.empty()
                    ? ""
                    : instruction.validation_status + (instruction.validation_command.empty() ? "" : " / " + instruction.validation_command));
                row("Completion", instruction.completion_status.empty()
                    ? ""
                    : instruction.completion_status + " / " + FormatPercent(instruction.completion_score, instruction.has_completion_score));
                row("Recommendation", instruction.recommendation);
                ImGui::EndTable();
            }

            ImGui::BeginDisabled(instruction.open_items <= 0 || busy_);
            if (ImGui::Button("Continue Instruction Work")) {
                SetBuffer(message_buffer_, instruction.recommendation.empty()
                    ? "continue working through the open project instruction items, validate the result, and update completed checklist items"
                    : instruction.recommendation);
                mode_ = "develop";
                apply_changes_ = true;
                run_validation_ = true;
                active_nav_ = "chat";
                status_ = "Loaded instruction checkpoint continuation into the composer.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(instruction.recommendation.empty());
            if (ImGui::Button("Copy Recommendation")) {
                ImGui::SetClipboardText(instruction.recommendation.c_str());
                status_ = "Copied instruction checkpoint recommendation.";
            }
            ImGui::EndDisabled();

            if (!instruction.files.empty() && ImGui::TreeNodeEx("Instruction Files", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (size_t i = 0; i < std::min<size_t>(instruction.files.size(), 8); ++i) {
                    const WorkspaceInstructionStatusFileInfo& file = instruction.files[i];
                    ImGui::BulletText(
                        "%s",
                        Shorten(
                            file.path + " - " +
                                std::to_string(file.open_items) + " open / " +
                                std::to_string(file.completed_items) + " done",
                            132)
                            .c_str());
                    if (!file.pending_items.empty()) {
                        ImGui::Indent(16.0f);
                        for (size_t item_index = 0; item_index < std::min<size_t>(file.pending_items.size(), 3); ++item_index) {
                            TextMuted("- " + Shorten(file.pending_items[item_index], 118));
                        }
                        ImGui::Unindent(16.0f);
                    }
                }
                ImGui::TreePop();
            }
        }

        if (workspace_profile_.has_validation_plan) {
            const WorkspaceValidationPlanInfo& plan = workspace_profile_.validation_plan;
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Validation Plan", Rgba(246, 248, 251));
            const bool failed = Lower(plan.last_run_status).find("fail") != std::string::npos ||
                Lower(plan.last_run_status).find("block") != std::string::npos;
            Pill(
                failed ? "Needs repair" : (plan.steps.empty() ? "Command only" : "Planned"),
                failed ? Rgba(248, 64, 82) : Rgba(38, 221, 123));
            ImGui::SameLine();
            TextMuted(
                std::to_string(plan.steps.size()) + " step" +
                (plan.steps.size() == 1 ? "" : "s") +
                (plan.validation_command.empty() ? "" : " / " + Shorten(plan.validation_command, 84)));

            if (ImGui::BeginTable("workspace_validation_plan_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Signal", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::string& value) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(value.empty() ? "-" : Shorten(value, 128));
                };
                row("Updated", plan.updated_at);
                row("Validate", plan.validation_command);
                row("Last Run", plan.last_run_status.empty()
                    ? ""
                    : plan.last_run_status + (plan.last_run_command.empty() ? "" : " / " + plan.last_run_command));
                row("Failed Step", plan.last_run_failed_step);
                row("Summary", plan.last_run_summary);
                ImGui::EndTable();
            }

            ImGui::BeginDisabled(plan.validation_command.empty());
            if (ImGui::Button("Copy Plan Command")) {
                ImGui::SetClipboardText(plan.validation_command.c_str());
                status_ = "Copied validation plan command.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(busy_ || (plan.last_run_failed_step.empty() && plan.last_run_command.empty()));
            if (ImGui::Button("Repair Validation Step")) {
                const std::string repair_target = plan.last_run_failed_step.empty()
                    ? plan.last_run_command
                    : plan.last_run_failed_step;
                SetBuffer(
                    message_buffer_,
                    "repair the saved validation plan step " + repair_target +
                        ", inspect the captured build output, apply the fix, and rerun validation until it passes");
                mode_ = "develop";
                apply_changes_ = true;
                run_validation_ = true;
                active_nav_ = "chat";
                status_ = "Loaded validation-plan repair prompt into the composer.";
            }
            ImGui::EndDisabled();

            if (!plan.steps.empty() && ImGui::TreeNodeEx("Validation Steps", ImGuiTreeNodeFlags_DefaultOpen)) {
                for (size_t i = 0; i < std::min<size_t>(plan.steps.size(), 8); ++i) {
                    const WorkspaceValidationPlanStepInfo& step = plan.steps[i];
                    std::string prefix = step.label.empty() ? step.id : step.label;
                    if (prefix.empty()) {
                        prefix = "Validation step " + std::to_string(i + 1);
                    }
                    if (step.chain_total > 1 && step.chain_index > 0) {
                        prefix += " (" + std::to_string(step.chain_index) + "/" + std::to_string(step.chain_total) + ")";
                    }
                    ImGui::BulletText("%s", Shorten(prefix + " - " + step.command, 148).c_str());
                }
                ImGui::TreePop();
            }
        }

        const WorkspaceDependencyProfileInfo& dependency = workspace_profile_.dependency_profile;
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Dependency Profile", Rgba(246, 248, 251));
        if (dependency.config_files.empty()) {
            TextMuted("No dependency or build manifest detected yet.");
        } else {
            if (ImGui::BeginTable("workspace_dependency_profile_table", 2, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Signal", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Detected");
                ImGui::TableHeadersRow();

                auto row = [](const char* label, const std::vector<std::string>& values) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    TextMuted(label);
                    ImGui::TableSetColumnIndex(1);
                    TextMuted(values.empty() ? "-" : Shorten(JoinPalette(values), 128));
                };
                if (!dependency.project_type.empty()) {
                    row("Project", std::vector<std::string>{dependency.project_type});
                }
                row("Languages", dependency.languages);
                row("Frameworks", dependency.frameworks);
                row("Managers", dependency.package_managers);
                row("Build", dependency.build_systems);
                row("Entry", dependency.entry_points);
                row("Tests", dependency.test_files);
                row("Database", dependency.database_tools);
                row("Configs", dependency.config_files);
                row("Install", dependency.install_commands);
                row("Validate", dependency.validation_commands);
                ImGui::EndTable();
            }

            ImGui::BeginDisabled(dependency.install_commands.empty());
            if (ImGui::Button("Copy Inferred Install")) {
                ImGui::SetClipboardText(dependency.install_commands.front().c_str());
                status_ = "Copied inferred install command.";
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            ImGui::BeginDisabled(dependency.validation_commands.empty());
            if (ImGui::Button("Copy Inferred Validate")) {
                ImGui::SetClipboardText(dependency.validation_commands.front().c_str());
                status_ = "Copied inferred validation command.";
            }
            ImGui::EndDisabled();

            if (!dependency.scripts.empty() && ImGui::TreeNode("Scripts")) {
                for (size_t i = 0; i < std::min<size_t>(dependency.scripts.size(), 12); ++i) {
                    const WorkspaceScriptInfo& script = dependency.scripts[i];
                    ImGui::BulletText("%s", Shorten(script.name + ": " + script.command, 132).c_str());
                }
                ImGui::TreePop();
            }
            if (!dependency.dependencies.empty() && ImGui::TreeNode("Runtime Dependencies")) {
                for (size_t i = 0; i < std::min<size_t>(dependency.dependencies.size(), 16); ++i) {
                    const WorkspaceDependencyInfo& item = dependency.dependencies[i];
                    const std::string version = item.version.empty() ? "" : " " + item.version;
                    ImGui::BulletText("%s", Shorten(item.name + version, 112).c_str());
                }
                ImGui::TreePop();
            }
            if (!dependency.dev_dependencies.empty() && ImGui::TreeNode("Development Dependencies")) {
                for (size_t i = 0; i < std::min<size_t>(dependency.dev_dependencies.size(), 16); ++i) {
                    const WorkspaceDependencyInfo& item = dependency.dev_dependencies[i];
                    const std::string version = item.version.empty() ? "" : " " + item.version;
                    ImGui::BulletText("%s", Shorten(item.name + version, 112).c_str());
                }
                ImGui::TreePop();
            }
            if (!dependency.warnings.empty()) {
                for (size_t i = 0; i < std::min<size_t>(dependency.warnings.size(), 3); ++i) {
                    TextColor("- " + Shorten(dependency.warnings[i], 128), Rgba(205, 154, 82));
                }
            }
        }
    } else if (!workspace_profile_error_.empty()) {
        TextMuted("Workspace profile unavailable: " + Shorten(workspace_profile_error_, 128));
    }
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
    if (has_verification_result_ && !verification_result_.events.empty()) {
        TextColor("Latest Verification Events", Rgba(246, 248, 251));
        for (const ToolEvent& event : verification_result_.events) {
            ImGui::TextWrapped("%s", event.title.c_str());
            TextMuted(event.detail);
            ImGui::SameLine(ImGui::GetWindowWidth() - 72.0f);
            Pill(event.status.c_str(), event.status == "error" ? StatusColor(false) : StatusColor(true));
            ImGui::Separator();
        }
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
    }

    const std::vector<ToolEvent>* events = has_response_ ? &last_response_.events : nullptr;
    if (events == nullptr || events->empty()) {
        if (!has_verification_result_) {
            TextMuted("Task events will appear after Aegis runs.");
        }
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

    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    TextColor("Runtime Health", Rgba(246, 248, 251));
    if (health_.ok || health_.engine_ready) {
        const std::string health_status = health_.status.empty() ? (health_.ready ? "ready" : "degraded") : health_.status;
        const bool runtime_ready = health_status == "ready" && health_.engine_ready;
        TextMuted(Shorten(
            (health_.app.empty() ? "Aegis Coding AI" : health_.app) +
            (health_.version.empty() ? "" : " " + health_.version) +
            " / " + (health_.engine.empty() ? "Aegis Core" : health_.engine),
            116));
        if (ImGui::BeginTable("settings_runtime_health_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Runtime", ImGuiTableColumnFlags_WidthFixed, 104.0f);
            ImGui::TableSetupColumn("Model");
            ImGui::TableSetupColumn("Providers", ImGuiTableColumnFlags_WidthFixed, 126.0f);
            ImGui::TableSetupColumn("Router", ImGuiTableColumnFlags_WidthFixed, 132.0f);
            ImGui::TableHeadersRow();
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            Pill(health_status.c_str(), runtime_ready ? Rgba(38, 221, 123) : Rgba(205, 154, 82));
            ImGui::TableSetColumnIndex(1);
            TextMuted(Shorten(
                (health_.model_api.empty() ? "model" : health_.model_api) +
                " / " + (health_.model_name.empty() ? config_.model_name : health_.model_name),
                58));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(health_.configured_provider_count) + " configured / " + std::to_string(health_.provider_count));
            ImGui::TableSetColumnIndex(3);
            TextMuted(std::string(health_.router_enabled ? "routes on" : "routes off") +
                (health_.fallback_supported ? " / fallback" : ""));
            ImGui::EndTable();
        }
        if (!health_.workspace_root.empty()) {
            TextMuted("Workspace: " + Shorten(health_.workspace_root, 104));
        }
        if (!health_.recommendations.empty()) {
            TextColor("Runtime recommendation: " + Shorten(health_.recommendations.front(), 112), Rgba(205, 154, 82));
        }
    } else {
        TextMuted("Runtime diagnostics appear after the backend handshake succeeds.");
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
    ImGui::Separator();
    ImGui::TextUnformatted("Feedback Privacy");
    TextMuted("Controls whether feedback memory can keep redacted snippets for preference review.");
    ImGui::Checkbox("Shared workspace mode", &config_.shared_workspace_mode);
    ImGui::Checkbox("Capture redacted excerpts", &config_.feedback_capture_excerpts);
    ImGui::Checkbox("Redact secrets and emails", &config_.feedback_redaction_enabled);
    ImGui::Checkbox("Store content hashes", &config_.feedback_hash_content);
    ImGui::SliderInt("Max feedback excerpt", &config_.feedback_max_excerpt_chars, 0, 2000);
    if (config_.shared_workspace_mode) {
        TextMuted("Shared mode disables feedback excerpts and content hashes on the backend.");
    }
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
    ImGui::SameLine();
    if (ImGui::Button("Full Verify")) {
        VerifyWorkspace();
    }
    ImGui::EndDisabled();
    ImGui::Checkbox("Include install step", &verification_include_install_);
    ImGui::SameLine();
    ImGui::Checkbox("Continue after failures", &verification_continue_on_failure_);
    ImGui::Checkbox("Auto repair next Full Verify failures", &verification_auto_repair_chain_);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(112.0f);
    ImGui::SliderInt("Chain limit", &verification_chain_repair_limit_, 1, 8);
    if (verification_chain_repairs_remaining_ > 0) {
        TextMuted("Repair chain: " + std::to_string(verification_chain_repairs_remaining_) + " queued repair pass(es) remaining.");
        ImGui::SameLine();
        if (ImGui::SmallButton("Stop chain")) {
            verification_chain_repairs_remaining_ = 0;
            pending_verification_chain_repair_ = false;
            pending_full_verify_after_repair_ = false;
            status_ = "Stopped the Full Verify repair chain.";
            TrackVerificationRepairActivity("Repair chain stopped", "Manual stop requested from Validation Profile.", "stopped");
        }
    }

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

    RenderVerificationResultPanel();
}

void AegisChatApp::RenderVerificationResultPanel()
{
    if (!has_verification_result_) {
        return;
    }

    const std::string status = verification_result_.status.empty() ? "skipped" : verification_result_.status;
    const auto status_color = [](const std::string& value) {
        const std::string lowered = Lower(value);
        if (lowered == "passed" || lowered == "succeeded") {
            return Rgba(38, 221, 123);
        }
        if (lowered == "failed" || lowered == "blocked") {
            return Rgba(248, 113, 113);
        }
        if (lowered == "running" || lowered == "planned") {
            return Rgba(205, 154, 82);
        }
        return Rgba(151, 160, 171);
    };

    int succeeded = 0;
    int failed = 0;
    int blocked = 0;
    for (const VerificationStepInfo& step : verification_result_.steps) {
        const std::string lowered = Lower(step.status);
        if (lowered == "succeeded") {
            ++succeeded;
        } else if (lowered == "blocked") {
            ++blocked;
        } else if (lowered == "failed") {
            ++failed;
        }
    }

    ImGui::Dummy(ImVec2(0.0f, 10.0f));
    ImGui::Separator();
    TextColor("Full Verification", Rgba(246, 248, 251));
    ImGui::SameLine();
    Pill(status.c_str(), status_color(status));
    TextMuted(
        std::to_string(verification_result_.steps.size()) + " step(s), " +
        std::to_string(succeeded) + " passed, " +
        std::to_string(failed) + " failed, " +
        std::to_string(blocked) + " blocked");
    if (ImGui::Button("Copy Verification Report")) {
        const std::string report = BuildVerificationReport(verification_result_, verification_repair_activities_);
        ImGui::SetClipboardText(report.c_str());
        status_ = "Copied verification report.";
    }
    ImGui::SameLine();
    if (ImGui::Button("Export Report")) {
        ExportVerificationReport();
    }
    ImGui::SameLine();
    if (ImGui::Button("Open Reports")) {
        OpenVerificationReportsFolder();
    }
    ImGui::SameLine();
    if (ImGui::Button("Prune Old Reports")) {
        PruneVerificationReports(25);
    }

    const std::vector<std::filesystem::path> recent_reports = RecentVerificationReportPaths(5);
    if (!recent_reports.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Recent Verification Reports", Rgba(246, 248, 251));
        if (ImGui::BeginTable("recent_verification_reports_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Report");
            ImGui::TableSetupColumn("Open", ImGuiTableColumnFlags_WidthFixed, 64.0f);
            ImGui::TableSetupColumn("Copy", ImGuiTableColumnFlags_WidthFixed, 64.0f);
            ImGui::TableSetupColumn("Attach", ImGuiTableColumnFlags_WidthFixed, 70.0f);
            ImGui::TableHeadersRow();
            for (int i = 0; i < static_cast<int>(recent_reports.size()); ++i) {
                const std::filesystem::path& path = recent_reports[static_cast<size_t>(i)];
                const std::string path_text = WideToUtf8(path.wstring());
                ImGui::PushID(i);
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextMuted(Shorten(WideToUtf8(path.filename().wstring()), 78));
                ImGui::TableSetColumnIndex(1);
                if (ImGui::Button("Open")) {
                    OpenExternalPath(path);
                    status_ = "Opened verification report.";
                }
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("Copy")) {
                    ImGui::SetClipboardText(path_text.c_str());
                    status_ = "Copied verification report path.";
                }
                ImGui::TableSetColumnIndex(3);
                if (ImGui::Button("Attach")) {
                    AttachVerificationReport(path_text);
                }
                ImGui::PopID();
            }
            ImGui::EndTable();
        }
    }

    if (!verification_repair_activities_.empty()) {
        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        TextColor("Verification Repair Activity", Rgba(246, 248, 251));
        TextMuted("Tracks Full Verify, targeted repair, failed-command validation, and automatic reruns.");
        if (ImGui::BeginTable("verification_repair_activity_table", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Time", ImGuiTableColumnFlags_WidthFixed, 72.0f);
            ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
            ImGui::TableSetupColumn("Step", ImGuiTableColumnFlags_WidthFixed, 168.0f);
            ImGui::TableSetupColumn("Detail");
            ImGui::TableHeadersRow();
            const int first = std::max(0, static_cast<int>(verification_repair_activities_.size()) - 8);
            for (int i = first; i < static_cast<int>(verification_repair_activities_.size()); ++i) {
                const VerificationRepairActivity& activity = verification_repair_activities_[static_cast<size_t>(i)];
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextMuted(activity.created_at.empty() ? "-" : activity.created_at);
                ImGui::TableSetColumnIndex(1);
                TextColor(Shorten(activity.status.empty() ? "info" : activity.status, 14), status_color(activity.status));
                ImGui::TableSetColumnIndex(2);
                TextColor(Shorten(activity.title.empty() ? "Verification" : activity.title, 30), Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(3);
                const std::string detail = activity.command.empty()
                    ? activity.detail
                    : (activity.detail.empty() ? activity.command : activity.detail + " | " + activity.command);
                TextMuted(Shorten(detail.empty() ? "-" : detail, 96));
            }
            ImGui::EndTable();
        }
    }

    if (verification_result_.has_first_failure) {
        const CommandRun& failure = verification_result_.first_failure;
        TextColor("First Failure", Rgba(248, 113, 113));
        TextMuted(Shorten(failure.summary.empty() ? failure.reason : failure.summary, 132));
        if (!failure.command.empty()) {
            TextMuted("Command: " + Shorten(failure.command, 132));
        }
        if (ImGui::Button("Copy Failure Output")) {
            const std::string output = ValidationCombinedOutput(failure);
            ImGui::SetClipboardText(output.empty() ? failure.summary.c_str() : output.c_str());
            status_ = "Copied verification failure output.";
        }
        ImGui::SameLine();
        ImGui::BeginDisabled(busy_);
        if (ImGui::Button("Repair First Failure")) {
            RepairLastValidationFailure();
        }
        ImGui::SameLine();
        if (ImGui::Button("Repair Until Clean")) {
            RepairLastValidationFailure(true);
        }
        ImGui::EndDisabled();
    }

    if (!verification_result_.warnings.empty()) {
        const int count = std::min(3, static_cast<int>(verification_result_.warnings.size()));
        for (int i = 0; i < count; ++i) {
            TextColor(Shorten(verification_result_.warnings[static_cast<size_t>(i)], 132), Rgba(205, 154, 82));
        }
    }

    if (verification_result_.steps.empty()) {
        TextMuted("No verification steps were detected.");
        return;
    }

    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    if (ImGui::BeginTable("verification_steps_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Phase", ImGuiTableColumnFlags_WidthFixed, 92.0f);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 88.0f);
        ImGui::TableSetupColumn("Command");
        ImGui::TableSetupColumn("Required", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableSetupColumn("Result");
        ImGui::TableHeadersRow();
        for (const VerificationStepInfo& step : verification_result_.steps) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(step.phase.empty() ? step.category : step.phase, 18));
            ImGui::TableSetColumnIndex(1);
            TextColor(Shorten(step.status.empty() ? "planned" : step.status, 18), status_color(step.status));
            ImGui::TableSetColumnIndex(2);
            TextColor(Shorten(step.command, 62), Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(3);
            TextMuted(step.required ? "yes" : "optional");
            ImGui::TableSetColumnIndex(4);
            std::string summary;
            if (step.has_run) {
                summary = step.run.summary.empty() ? step.run.reason : step.run.summary;
            } else {
                summary = step.reason;
            }
            TextMuted(Shorten(summary.empty() ? "-" : summary, 72));
        }
        ImGui::EndTable();
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
        RefreshRuntime(true);
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
        RefreshRuntime(true);
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
    TextColor("Local Model Storage", Rgba(246, 248, 251));
    TextMuted(model_manager_.message.empty()
        ? "Disk-aware model manager data will appear after the backend refreshes."
        : model_manager_.message);
    if (model_manager_.disk.total_bytes > 0) {
        const float free_fraction = static_cast<float>(std::max(0.0, std::min(100.0, model_manager_.disk.free_percent)) / 100.0);
        DrawProgress(free_fraction, ImVec2(ImGui::GetContentRegionAvail().x, 8.0f), model_manager_.disk.low_space);
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        if (ImGui::BeginTable("model_storage_summary", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Free", ImGuiTableColumnFlags_WidthFixed, 130.0f);
            ImGui::TableSetupColumn("Model Store", ImGuiTableColumnFlags_WidthFixed, 130.0f);
            ImGui::TableSetupColumn("Reserve", ImGuiTableColumnFlags_WidthFixed, 130.0f);
            ImGui::TableSetupColumn("Path");
            ImGui::TableHeadersRow();
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextColor(FormatModelBytes(model_manager_.disk.free_bytes), model_manager_.disk.low_space ? Rgba(248, 113, 113) : Rgba(38, 221, 123));
            ImGui::TableSetColumnIndex(1);
            TextMuted(FormatModelBytes(model_manager_.disk.model_store_bytes));
            ImGui::TableSetColumnIndex(2);
            TextMuted(FormatModelBytes(model_manager_.disk.minimum_free_bytes));
            ImGui::TableSetColumnIndex(3);
            TextMuted(Shorten(model_manager_.disk.model_store_path.empty() ? model_manager_.disk.project_root : model_manager_.disk.model_store_path, 78));
            ImGui::EndTable();
        }
    }
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Model Manager")) {
        RefreshModelManager();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(model_manager_.disk.model_store_path.empty());
    if (ImGui::Button("Open Model Store")) {
        OpenExternalPath(std::filesystem::path(Utf8ToWide(model_manager_.disk.model_store_path)));
        status_ = "Opened local model store.";
    }
    ImGui::EndDisabled();

    ImGui::Separator();
    TextColor("Agent Routing Readiness", Rgba(246, 248, 251));
    TextMuted("Aegis becomes stronger when each task can route to a specialist and fall back cleanly if that provider fails.");
    if (ImGui::BeginTable("agent_route_readiness_table", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Route", ImGuiTableColumnFlags_WidthFixed, 104.0f);
        ImGui::TableSetupColumn("State", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Ready", ImGuiTableColumnFlags_WidthFixed, 58.0f);
        ImGui::TableSetupColumn("Providers");
        ImGui::TableSetupColumn("Good Next Provider", ImGuiTableColumnFlags_WidthFixed, 190.0f);
        ImGui::TableHeadersRow();
        for (const AgentRouteBlueprint& route : kAgentRouteBlueprints) {
            const int ready = CountProvidersForRoute(model_registry_, route, true);
            const int enabled = CountProvidersForRoute(model_registry_, route, false);
            const int staged = std::max(0, enabled - ready);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextColor(route.label, ready > 0 ? Rgba(38, 221, 123) : (staged > 0 ? Rgba(205, 154, 82) : Rgba(248, 113, 113)));
            ImGui::TableSetColumnIndex(1);
            Pill(ready > 0 ? "Ready" : (staged > 0 ? "Staged" : "Gap"),
                 ready > 0 ? Rgba(38, 221, 123) : (staged > 0 ? Rgba(205, 154, 82) : Rgba(248, 113, 113)));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(ready) + (staged > 0 ? " + " + std::to_string(staged) : ""));
            ImGui::TableSetColumnIndex(3);
            TextMuted(Shorten(ProviderLabelsForRoute(model_registry_, route, false), 62));
            ImGui::TableSetColumnIndex(4);
            TextMuted(route.recommended);
        }
        ImGui::EndTable();
    }

    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    TextColor("Registry Checkpoints", Rgba(246, 248, 251));
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Create Baseline")) {
        CreateModelRegistryCheckpoint();
    }
    ImGui::EndDisabled();
    if (!model_registry_checkpoints_error_.empty()) {
        TextColor("Checkpoint history unavailable: " + Shorten(model_registry_checkpoints_error_, 118), Rgba(248, 113, 113));
    } else if (!model_registry_checkpoints_loaded_) {
        TextMuted("Refresh Model Manager to load provider and routing rollback points.");
    } else if (model_registry_checkpoints_.checkpoints.empty()) {
        TextMuted("No registry checkpoints yet. Provider edits and healthy-winner applies will create rollback points.");
    } else if (ImGui::BeginTable("model_registry_checkpoints_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Created", ImGuiTableColumnFlags_WidthFixed, 146.0f);
        ImGui::TableSetupColumn("Reason");
        ImGui::TableSetupColumn("Snapshot", ImGuiTableColumnFlags_WidthFixed, 100.0f);
        ImGui::TableSetupColumn("Restore Impact", ImGuiTableColumnFlags_WidthFixed, 190.0f);
        ImGui::TableSetupColumn("Details", ImGuiTableColumnFlags_WidthFixed, 76.0f);
        ImGui::TableSetupColumn("Restore", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableHeadersRow();
        const int visible_checkpoints = std::min(4, static_cast<int>(model_registry_checkpoints_.checkpoints.size()));
        for (int i = 0; i < visible_checkpoints; ++i) {
            const ModelRegistryCheckpointInfo& checkpoint = model_registry_checkpoints_.checkpoints[static_cast<size_t>(i)];
            const bool restore_changes = checkpoint.restore_total_change_count > 0;
            const bool restore_pending = has_pending_model_registry_restore_ && pending_model_registry_restore_.id == checkpoint.id;
            ImGui::PushID(checkpoint.id.empty() ? i : static_cast<int>(std::hash<std::string>{}(checkpoint.id)));
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(checkpoint.created_at.empty() ? checkpoint.id : checkpoint.created_at, 24));
            ImGui::TableSetColumnIndex(1);
            TextMuted(Shorten(checkpoint.reason.empty() ? checkpoint.message : checkpoint.reason, 72));
            ImGui::TableSetColumnIndex(2);
            TextMuted("P" + std::to_string(checkpoint.provider_count) + " / R" + std::to_string(checkpoint.role_count));
            ImGui::TableSetColumnIndex(3);
            TextColor(
                Shorten(checkpoint.restore_summary.empty() ? "Impact unknown" : checkpoint.restore_summary, 48),
                restore_changes ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
            ImGui::TableSetColumnIndex(4);
            ImGui::BeginDisabled(busy_ || checkpoint.id.empty());
            if (ImGui::Button("View", ImVec2(-1.0f, 0.0f))) {
                LoadModelRegistryCheckpointDiff(checkpoint);
            }
            ImGui::EndDisabled();
            ImGui::TableSetColumnIndex(5);
            ImGui::BeginDisabled(busy_ || checkpoint.id.empty());
            if (ImGui::Button(restore_pending ? "Pending" : "Restore", ImVec2(-1.0f, 0.0f))) {
                RequestModelRegistryCheckpointRestore(checkpoint);
            }
            ImGui::EndDisabled();
            ImGui::PopID();
        }
        ImGui::EndTable();
    }

    if (!selected_model_registry_checkpoint_diff_error_.empty()) {
        TextColor("Checkpoint details unavailable: " + Shorten(selected_model_registry_checkpoint_diff_error_, 118), Rgba(248, 113, 113));
        if (has_pending_model_registry_restore_) {
            ImGui::SameLine();
            if (ImGui::Button("Cancel Restore")) {
                has_pending_model_registry_restore_ = false;
                status_ = "Cancelled pending registry restore.";
            }
        }
    } else if (selected_model_registry_checkpoint_diff_loaded_) {
        const ModelRegistryCheckpointDiffInfo& diff = selected_model_registry_checkpoint_diff_;
        const bool restore_pending = has_pending_model_registry_restore_ && pending_model_registry_restore_.id == diff.checkpoint.id;
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
        TextColor("Checkpoint Details", Rgba(246, 248, 251));
        TextMuted(Shorten(diff.checkpoint.id + " / " + (diff.checkpoint.restore_summary.empty() ? "Impact unknown" : diff.checkpoint.restore_summary), 132));
        if (!diff.provider_diffs.empty() &&
            ImGui::BeginTable("model_registry_checkpoint_provider_diffs", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 128.0f);
            ImGui::TableSetupColumn("Current");
            ImGui::TableSetupColumn("Checkpoint");
            ImGui::TableHeadersRow();
            for (const ModelRegistryCheckpointEntityDiffInfo& item : diff.provider_diffs) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(Shorten(item.label.empty() ? item.id : item.label, 34), Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                Pill(item.action.empty() ? "change" : item.action.c_str(), item.action == "remove_on_restore" ? Rgba(248, 113, 113) : Rgba(205, 154, 82));
                ImGui::TableSetColumnIndex(2);
                TextMuted(Shorten(item.current_summary, 58));
                ImGui::TableSetColumnIndex(3);
                TextMuted(Shorten(item.checkpoint_summary, 58));
            }
            ImGui::EndTable();
        }
        if (!diff.role_diffs.empty() &&
            ImGui::BeginTable("model_registry_checkpoint_role_diffs", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 128.0f);
            ImGui::TableSetupColumn("Current");
            ImGui::TableSetupColumn("Checkpoint");
            ImGui::TableHeadersRow();
            for (const ModelRegistryCheckpointEntityDiffInfo& item : diff.role_diffs) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(Shorten(item.label.empty() ? item.id : item.label, 34), Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                Pill(item.action.empty() ? "change" : item.action.c_str(), item.action == "remove_on_restore" ? Rgba(248, 113, 113) : Rgba(205, 154, 82));
                ImGui::TableSetColumnIndex(2);
                TextMuted(Shorten(item.current_summary, 58));
                ImGui::TableSetColumnIndex(3);
                TextMuted(Shorten(item.checkpoint_summary, 58));
            }
            ImGui::EndTable();
        }
        if (!diff.setting_diffs.empty() &&
            ImGui::BeginTable("model_registry_checkpoint_setting_diffs", 3, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Setting", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableSetupColumn("Current");
            ImGui::TableSetupColumn("Checkpoint");
            ImGui::TableHeadersRow();
            for (const ModelRegistryCheckpointSettingDiffInfo& item : diff.setting_diffs) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(item.key, Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                TextMuted(item.current_value);
                ImGui::TableSetColumnIndex(2);
                TextMuted(item.checkpoint_value);
            }
            ImGui::EndTable();
        }
        if (diff.provider_diffs.empty() && diff.role_diffs.empty() && diff.setting_diffs.empty()) {
            TextMuted("No provider, role, or registry setting differences. This checkpoint matches the current registry.");
        }
        if (restore_pending) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextColor("Restore Confirmation", Rgba(205, 154, 82));
            TextMuted("Review the checkpoint details above. Confirming will overwrite the current model registry with this checkpoint.");
            ImGui::BeginDisabled(busy_);
            if (ImGui::Button("Confirm Restore")) {
                RestoreModelRegistryCheckpoint(pending_model_registry_restore_);
            }
            ImGui::EndDisabled();
            ImGui::SameLine();
            if (ImGui::Button("Cancel Restore")) {
                has_pending_model_registry_restore_ = false;
                status_ = "Cancelled pending registry restore.";
            }
        }
    }

    ImGui::Separator();
    TextColor("Benchmark Lab", Rgba(246, 248, 251));
    TextMuted(model_benchmarks_.message.empty()
        ? "Run a quick local benchmark to rank installed models for chat, code, and reasoning routes."
        : model_benchmarks_.message);
    const bool benchmark_job_active = HasActiveBenchmarkJob(model_benchmarks_);
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Scores")) {
        RefreshModelBenchmarks();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_ || benchmark_job_active);
    if (ImGui::Button("Run Quick Benchmark")) {
        RunQuickModelBenchmarks();
    }
    ImGui::SameLine();
    if (ImGui::Button("Seed Code + Reason")) {
        RunModelBenchmarkPreset("code and reasoning benchmark seed", {"code", "reasoning"}, 4, 55.0);
    }
    ImGui::SameLine();
    if (ImGui::Button("Deep Local Sweep")) {
        RunModelBenchmarkPreset("deep local benchmark sweep", {"chat", "code", "reasoning"}, 8, 70.0);
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    ImGui::BeginDisabled(busy_ || benchmark_job_active || model_benchmarks_.provider_scores.empty());
    if (ImGui::Button("Apply Healthy Winners")) {
        ApplyBenchmarkWinnersToRoutes();
    }
    ImGui::EndDisabled();
    if (!model_benchmarks_.latest_at.empty()) {
        ImGui::SameLine();
        TextMuted("Latest: " + Shorten(model_benchmarks_.latest_at, 24));
    }
    if (benchmark_job_active) {
        ImGui::SameLine();
        TextColor("Benchmark running", Rgba(38, 221, 123));
    }
    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    TextColor("Healthy Apply Preview", Rgba(246, 248, 251));
    if (!route_apply_preview_error_.empty()) {
        TextColor("Preview unavailable: " + Shorten(route_apply_preview_error_, 126), Rgba(248, 113, 113));
    } else if (route_apply_preview_loaded_) {
        const int change_count = static_cast<int>(std::count_if(
            route_apply_preview_.role_diffs.begin(),
            route_apply_preview_.role_diffs.end(),
            [](const ModelRegistryRoleDiffInfo& diff) { return diff.action != "keep"; }));
        const std::string summary = route_apply_preview_.message.empty()
            ? ("Dry run ready: " + std::to_string(change_count) + " route change(s) would apply.")
            : route_apply_preview_.message;
        TextMuted(summary);
        if (!route_apply_preview_.role_diffs.empty() &&
            ImGui::BeginTable("benchmark_route_apply_preview", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Role", ImGuiTableColumnFlags_WidthFixed, 76.0f);
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 116.0f);
            ImGui::TableSetupColumn("Current", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableSetupColumn("Proposed");
            ImGui::TableSetupColumn("Fallbacks", ImGuiTableColumnFlags_WidthFixed, 190.0f);
            ImGui::TableSetupColumn("Health", ImGuiTableColumnFlags_WidthFixed, 150.0f);
            ImGui::TableHeadersRow();
            for (const ModelRegistryRoleDiffInfo& diff : route_apply_preview_.role_diffs) {
                const bool risky = diff.health_cooldown;
                const bool changed = diff.action != "keep";
                const ImVec4 action_color = risky
                    ? Rgba(248, 113, 113)
                    : (changed ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
                const std::string health = diff.health_cooldown
                    ? "cooldown"
                    : (diff.health_penalty > 0.0 ? "penalty " + std::to_string(static_cast<int>(diff.health_penalty)) : "clear");
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(diff.role.empty() ? "route" : diff.role, Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                Pill(diff.action.empty() ? "keep" : diff.action.c_str(), action_color);
                ImGui::TableSetColumnIndex(2);
                TextMuted(Shorten(diff.current_primary_model.empty() ? "none" : diff.current_primary_model, 34));
                ImGui::TableSetColumnIndex(3);
                TextColor(
                    Shorten(diff.proposed_primary_model.empty() ? diff.winner_provider_id : diff.proposed_primary_model, 44),
                    changed ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(4);
                TextMuted(Shorten(JoinList(diff.proposed_fallback_models), 44));
                ImGui::TableSetColumnIndex(5);
                TextMuted(Shorten(diff.health_recommendation.empty() ? health : health + " / " + diff.health_recommendation, 46));
            }
            ImGui::EndTable();
        }
        if (!route_apply_preview_.warnings.empty()) {
            for (size_t i = 0; i < std::min<size_t>(2, route_apply_preview_.warnings.size()); ++i) {
                TextColor("- " + Shorten(route_apply_preview_.warnings[i], 126), Rgba(248, 113, 113));
            }
        } else if (!route_apply_preview_.recommendations.empty()) {
            TextMuted("- " + Shorten(route_apply_preview_.recommendations.front(), 132));
        }
    } else {
        TextMuted("Refresh Scores to load the dry-run route changes before applying benchmark winners.");
    }
    if (!model_benchmarks_.jobs.empty() &&
        ImGui::BeginTable("model_benchmark_jobs_table", 6, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Job", ImGuiTableColumnFlags_WidthFixed, 146.0f);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 88.0f);
        ImGui::TableSetupColumn("Progress", ImGuiTableColumnFlags_WidthFixed, 92.0f);
        ImGui::TableSetupColumn("Current");
        ImGui::TableSetupColumn("Message", ImGuiTableColumnFlags_WidthFixed, 216.0f);
        ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 76.0f);
        ImGui::TableHeadersRow();
        const int job_count = std::min(3, static_cast<int>(model_benchmarks_.jobs.size()));
        for (int i = 0; i < job_count; ++i) {
            const ModelBenchmarkJobInfo& job = model_benchmarks_.jobs[static_cast<size_t>(i)];
            const bool active_job = job.status == "queued" || job.status == "running" || job.status == "cancel_requested";
            if (job.id.empty()) {
                ImGui::PushID(i);
            } else {
                ImGui::PushID(job.id.c_str());
            }
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(job.id.empty() ? "benchmark" : job.id, 24));
            ImGui::TableSetColumnIndex(1);
            Pill(job.status.empty() ? "unknown" : job.status.c_str(),
                 active_job ? Rgba(38, 221, 123) : (job.status == "failed" || job.status == "interrupted" ? Rgba(248, 113, 113) : Rgba(133, 146, 161)));
            ImGui::TableSetColumnIndex(2);
            TextMuted(std::to_string(job.completed_runs) + "/" + std::to_string(job.total_runs));
            ImGui::TableSetColumnIndex(3);
            TextMuted(Shorten(job.current_model_name.empty() ? "-" : job.current_model_name + " / " + job.current_suite_id, 54));
            ImGui::TableSetColumnIndex(4);
            TextMuted(Shorten(job.error.empty() ? job.message : job.error, 72));
            ImGui::TableSetColumnIndex(5);
            ImGui::BeginDisabled(busy_ || !active_job || job.status == "cancel_requested");
            if (ImGui::Button("Cancel", ImVec2(-1.0f, 0.0f))) {
                CancelModelBenchmarkJob(job);
            }
            ImGui::EndDisabled();
            ImGui::PopID();
        }
        ImGui::EndTable();
    }
    if (!model_benchmarks_.suite_summaries.empty() &&
        ImGui::BeginTable("model_benchmark_suite_summary", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Suite", ImGuiTableColumnFlags_WidthFixed, 112.0f);
        ImGui::TableSetupColumn("Best Model");
        ImGui::TableSetupColumn("Score", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableSetupColumn("Latency", ImGuiTableColumnFlags_WidthFixed, 82.0f);
        ImGui::TableSetupColumn("Runs", ImGuiTableColumnFlags_WidthFixed, 58.0f);
        ImGui::TableHeadersRow();
        for (const ModelBenchmarkSuiteSummaryInfo& summary : model_benchmarks_.suite_summaries) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextColor(summary.suite_label.empty() ? summary.suite_id : summary.suite_label, summary.best_score >= 0.75 ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(1);
            TextMuted(summary.best_model_name.empty() ? "No benchmark data" : Shorten(summary.best_model_name, 54));
            ImGui::TableSetColumnIndex(2);
            TextMuted(summary.best_model_name.empty() ? "-" : FormatPercent(summary.best_score));
            ImGui::TableSetColumnIndex(3);
            TextMuted(summary.has_best_latency_ms ? std::to_string(summary.best_latency_ms) + " ms" : "-");
            ImGui::TableSetColumnIndex(4);
            TextMuted(std::to_string(summary.run_count));
        }
        ImGui::EndTable();
    }
    if (!model_benchmarks_.provider_scores.empty() &&
        ImGui::BeginTable("model_benchmark_provider_scores", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 132.0f);
        ImGui::TableSetupColumn("Model");
        ImGui::TableSetupColumn("Overall", ImGuiTableColumnFlags_WidthFixed, 76.0f);
        ImGui::TableSetupColumn("Chat", ImGuiTableColumnFlags_WidthFixed, 68.0f);
        ImGui::TableSetupColumn("Code", ImGuiTableColumnFlags_WidthFixed, 68.0f);
        ImGui::TableSetupColumn("Reason", ImGuiTableColumnFlags_WidthFixed, 68.0f);
        ImGui::TableSetupColumn("Fit", ImGuiTableColumnFlags_WidthFixed, 190.0f);
        ImGui::TableHeadersRow();
        const int visible_scores = std::min(8, static_cast<int>(model_benchmarks_.provider_scores.size()));
        for (int i = 0; i < visible_scores; ++i) {
            const ModelBenchmarkProviderScoreInfo& score = model_benchmarks_.provider_scores[static_cast<size_t>(i)];
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            TextMuted(Shorten(score.provider_label.empty() ? score.provider_id : score.provider_label, 28));
            ImGui::TableSetColumnIndex(1);
            TextColor(Shorten(score.model_name.empty() ? score.provider_id : score.model_name, 42), i == 0 ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextColor(FormatPercent(score.overall_score), score.overall_score >= 0.75 ? Rgba(38, 221, 123) : Rgba(205, 154, 82));
            ImGui::TableSetColumnIndex(3);
            TextMuted(FormatPercent(score.chat_score, score.has_chat_score));
            ImGui::TableSetColumnIndex(4);
            TextMuted(FormatPercent(score.code_score, score.has_code_score));
            ImGui::TableSetColumnIndex(5);
            TextMuted(FormatPercent(score.reasoning_score, score.has_reasoning_score));
            ImGui::TableSetColumnIndex(6);
            TextMuted(Shorten(score.recommendation.empty() ? "-" : score.recommendation, 42));
        }
        ImGui::EndTable();
    }
    if (!model_benchmarks_.recommendations.empty()) {
        for (size_t i = 0; i < std::min<size_t>(3, model_benchmarks_.recommendations.size()); ++i) {
            TextMuted("- " + Shorten(model_benchmarks_.recommendations[i], 132));
        }
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
    TextColor("Managed Model Library", Rgba(246, 248, 251));
    TextMuted("Pull missing local Ollama models when there is enough C-drive headroom, or remove inactive installed models to reclaim space.");
    if (!model_manager_.pull_logs.empty()) {
        if (ImGui::BeginTable("model_pull_log_summary", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Pack", ImGuiTableColumnFlags_WidthFixed, 140.0f);
            ImGui::TableSetupColumn("Pulled", ImGuiTableColumnFlags_WidthFixed, 68.0f);
            ImGui::TableSetupColumn("Skipped", ImGuiTableColumnFlags_WidthFixed, 72.0f);
            ImGui::TableSetupColumn("Failed", ImGuiTableColumnFlags_WidthFixed, 64.0f);
            ImGui::TableSetupColumn("Latest");
            ImGui::TableHeadersRow();
            for (const ModelPullLogSummaryInfo& summary : model_manager_.pull_logs) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextMuted(summary.source.empty() ? "pull log" : summary.source);
                ImGui::TableSetColumnIndex(1);
                TextColor(std::to_string(summary.pulled), summary.pulled > 0 ? Rgba(38, 221, 123) : Rgba(133, 146, 161));
                ImGui::TableSetColumnIndex(2);
                TextMuted(std::to_string(summary.skipped));
                ImGui::TableSetColumnIndex(3);
                TextColor(std::to_string(summary.failed), summary.failed > 0 ? Rgba(248, 113, 113) : Rgba(133, 146, 161));
                ImGui::TableSetColumnIndex(4);
                TextMuted(Shorten(summary.latest_at, 48));
            }
            ImGui::EndTable();
        }
        ImGui::Dummy(ImVec2(0.0f, 6.0f));
    }
    if (!model_manager_.operations.empty()) {
        const ModelOperationInfo& latest = model_manager_.operations.front();
        TextMuted("Latest operation: " + latest.action + " " + latest.model_name + " - " + latest.status);
    }
    if (model_manager_.models.empty()) {
        TextMuted("No managed model records are loaded yet.");
    } else if (ImGui::BeginTable("managed_model_library_table", 9, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("State", ImGuiTableColumnFlags_WidthFixed, 78.0f);
        ImGui::TableSetupColumn("Model");
        ImGui::TableSetupColumn("Roles", ImGuiTableColumnFlags_WidthFixed, 150.0f);
        ImGui::TableSetupColumn("Size", ImGuiTableColumnFlags_WidthFixed, 84.0f);
        ImGui::TableSetupColumn("Pull Est.", ImGuiTableColumnFlags_WidthFixed, 84.0f);
        ImGui::TableSetupColumn("Health", ImGuiTableColumnFlags_WidthFixed, 118.0f);
        ImGui::TableSetupColumn("Pull", ImGuiTableColumnFlags_WidthFixed, 64.0f);
        ImGui::TableSetupColumn("Bench", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableSetupColumn("Remove", ImGuiTableColumnFlags_WidthFixed, 72.0f);
        ImGui::TableHeadersRow();
        const int visible_count = std::min(36, static_cast<int>(model_manager_.models.size()));
        for (int i = 0; i < visible_count; ++i) {
            const ManagedModelInfo& model = model_manager_.models[static_cast<size_t>(i)];
            ImGui::PushID(i);
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            const bool ready = model.installed || model.configured;
            Pill(model.active ? "Active" : (ready ? "Ready" : (model.pullable ? "Pull" : "Cloud")),
                 model.active || ready ? Rgba(38, 221, 123) : (model.pullable ? Rgba(205, 154, 82) : Rgba(133, 146, 161)));
            ImGui::TableSetColumnIndex(1);
            TextColor(Shorten(model.name.empty() ? model.provider_id : model.name, 42), model.active ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
            ImGui::TableSetColumnIndex(2);
            TextMuted(Shorten(JoinPalette(model.roles), 36));
            ImGui::TableSetColumnIndex(3);
            TextMuted(model.has_size_bytes ? FormatModelBytes(model.size_bytes) : "-");
            ImGui::TableSetColumnIndex(4);
            TextMuted(model.has_estimated_pull_bytes ? FormatModelBytes(model.estimated_pull_bytes) : "-");
            ImGui::TableSetColumnIndex(5);
            TextMuted(Shorten(model.health.empty() ? model.notes : model.health, 24));
            ImGui::TableSetColumnIndex(6);
            const bool can_pull = model.pullable && !model_manager_.disk.low_space && !busy_;
            ImGui::BeginDisabled(!can_pull);
            if (ImGui::Button("Pull", ImVec2(-1.0f, 0.0f))) {
                PullManagedModel(model);
            }
            ImGui::EndDisabled();
            if (!can_pull && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                ImGui::SetTooltip("%s", model_manager_.disk.low_space ? "Free more disk or lower reserve before pulling." : "Model is already installed, cloud-only, disabled, or busy.");
            }
            ImGui::TableSetColumnIndex(7);
            const bool can_benchmark = !busy_ && !benchmark_job_active && CanBenchmarkManagedModel(model);
            ImGui::BeginDisabled(!can_benchmark);
            if (ImGui::Button("Bench", ImVec2(-1.0f, 0.0f))) {
                RunManagedModelBenchmark(model);
            }
            ImGui::EndDisabled();
            if (!can_benchmark && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                ImGui::SetTooltip("%s", "Only installed local chat, code, or reasoning models can be benchmarked.");
            }
            ImGui::TableSetColumnIndex(8);
            const bool can_remove = model.local && model.installed && !model.active && !busy_;
            ImGui::BeginDisabled(!can_remove);
            if (ImGui::Button("Remove", ImVec2(-1.0f, 0.0f))) {
                DeleteManagedModel(model);
            }
            ImGui::EndDisabled();
            if (!can_remove && ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
                ImGui::SetTooltip("%s", model.active ? "Select another active model before removing this one." : "Only inactive installed local Ollama models can be removed.");
            }
            ImGui::PopID();
        }
        ImGui::EndTable();
        if (model_manager_.models.size() > static_cast<size_t>(visible_count)) {
            TextMuted("Showing " + std::to_string(visible_count) + " of " + std::to_string(model_manager_.models.size()) + " managed model records.");
        }
    }

    ImGui::Separator();
    TextColor("Provider Registry", Rgba(246, 248, 251));
    TextMuted(model_registry_.message.empty()
        ? "Provider registry will appear after the backend refreshes to the latest code."
        : model_registry_.message);

    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    TextColor("Registry Audit", Rgba(246, 248, 251));
    if (!model_registry_audit_error_.empty()) {
        TextColor("Audit unavailable: " + Shorten(model_registry_audit_error_, 126), Rgba(248, 113, 113));
    } else if (model_registry_audit_loaded_) {
        const bool blocked = model_registry_audit_.status == "blocked";
        const bool ready = model_registry_audit_.status == "ready";
        ImGui::Columns(4, "model_registry_audit_summary", false);
        TextMuted("Score");
        TextColor(std::to_string(model_registry_audit_.readiness_score) + "/100",
            blocked ? Rgba(248, 113, 113) : (ready ? Rgba(38, 221, 123) : Rgba(205, 154, 82)));
        ImGui::NextColumn();
        TextMuted("Providers");
        TextColor(
            std::to_string(model_registry_audit_.configured_provider_count) + " configured / " +
                std::to_string(model_registry_audit_.provider_count),
            Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Routes");
        TextColor(std::to_string(model_registry_audit_.role_count) + " roles", Rgba(246, 248, 251));
        ImGui::NextColumn();
        TextMuted("Issues");
        TextColor(std::to_string(model_registry_audit_.issues.size()),
            model_registry_audit_.issues.empty() ? Rgba(38, 221, 123) : Rgba(205, 154, 82));
        ImGui::Columns(1);
        DrawProgress(std::clamp(model_registry_audit_.readiness_score / 100.0f, 0.0f, 1.0f), ImVec2(ImGui::GetContentRegionAvail().x, 8.0f), blocked);
        if (!model_registry_audit_.route_coverages.empty() &&
            ImGui::BeginTable("model_registry_audit_routes", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
            ImGui::TableSetupColumn("Route", ImGuiTableColumnFlags_WidthFixed, 118.0f);
            ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 86.0f);
            ImGui::TableSetupColumn("Primary");
            ImGui::TableSetupColumn("Configured", ImGuiTableColumnFlags_WidthFixed, 92.0f);
            ImGui::TableSetupColumn("Fallbacks", ImGuiTableColumnFlags_WidthFixed, 82.0f);
            ImGui::TableHeadersRow();
            const int route_count = std::min(6, static_cast<int>(model_registry_audit_.route_coverages.size()));
            for (int i = 0; i < route_count; ++i) {
                const ModelRegistryRouteCoverageInfo& route = model_registry_audit_.route_coverages[static_cast<size_t>(i)];
                const bool route_ready = route.status == "ready";
                const bool route_missing = route.status == "missing";
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                TextColor(route.label.empty() ? route.role : route.label, route_ready ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
                ImGui::TableSetColumnIndex(1);
                Pill(route.status.empty() ? "unknown" : route.status.c_str(),
                    route_ready ? Rgba(38, 221, 123) : (route_missing ? Rgba(248, 113, 113) : Rgba(205, 154, 82)));
                ImGui::TableSetColumnIndex(2);
                TextMuted(route.primary_model.empty() ? "-" : Shorten(route.primary_model, 42));
                ImGui::TableSetColumnIndex(3);
                TextMuted(std::to_string(route.configured_provider_count) + " / " + std::to_string(route.eligible_provider_count));
                ImGui::TableSetColumnIndex(4);
                TextMuted(std::to_string(route.fallback_configured_count));
            }
            ImGui::EndTable();
        }
        if (!model_registry_audit_.setup_actions.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
            TextColor("Next Setup Actions", Rgba(246, 248, 251));
            const int action_count = std::min(5, static_cast<int>(model_registry_audit_.setup_actions.size()));
            if (ImGui::BeginTable("model_registry_setup_actions", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Priority", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 180.0f);
                ImGui::TableSetupColumn("Detail");
                ImGui::TableSetupColumn("Copy", ImGuiTableColumnFlags_WidthFixed, 62.0f);
                ImGui::TableHeadersRow();
                for (int i = 0; i < action_count; ++i) {
                    const ModelRegistrySetupActionInfo& action = model_registry_audit_.setup_actions[static_cast<size_t>(i)];
                    const bool critical = action.priority == "critical";
                    const bool high = action.priority == "high";
                    const bool low = action.priority == "low";
                    const ImVec4 priority_color = critical ? Rgba(248, 113, 113) : (high ? Rgba(205, 154, 82) : (low ? Rgba(151, 160, 171) : Rgba(82, 196, 205)));
                    const std::string priority = action.priority.empty() ? "medium" : action.priority;
                    const std::string title = action.title.empty() ? action.kind : action.title;
                    const std::string copy_text = action.command.empty() ? action.env_var : action.command;
                    ImGui::PushID(i);
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    Pill(Shorten(priority, 10).c_str(), priority_color);
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(title, 34), Rgba(246, 248, 251));
                    if (!action.kind.empty()) {
                        TextMuted(Shorten(action.kind, 20));
                    }
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(action.detail, 92));
                    if (!action.recommendation.empty()) {
                        TextMuted(Shorten(action.recommendation, 92));
                    }
                    ImGui::TableSetColumnIndex(3);
                    ImGui::BeginDisabled(copy_text.empty());
                    if (ImGui::Button("Copy")) {
                        ImGui::SetClipboardText(copy_text.c_str());
                        status_ = action.command.empty() ? "Copied setup environment variable." : "Copied setup command.";
                    }
                    ImGui::EndDisabled();
                    ImGui::PopID();
                }
                ImGui::EndTable();
            }
        }
        if (!model_registry_audit_.adapter_health.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 4.0f));
            TextColor("Adapter Health", Rgba(246, 248, 251));
            const int adapter_count = std::min(8, static_cast<int>(model_registry_audit_.adapter_health.size()));
            if (ImGui::BeginTable("model_registry_adapter_health", 7, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 104.0f);
                ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 154.0f);
                ImGui::TableSetupColumn("API", ImGuiTableColumnFlags_WidthFixed, 86.0f);
                ImGui::TableSetupColumn("Model", ImGuiTableColumnFlags_WidthFixed, 142.0f);
                ImGui::TableSetupColumn("Attempts", ImGuiTableColumnFlags_WidthFixed, 112.0f);
                ImGui::TableSetupColumn("Secret", ImGuiTableColumnFlags_WidthFixed, 132.0f);
                ImGui::TableSetupColumn("Message");
                ImGui::TableHeadersRow();
                for (int i = 0; i < adapter_count; ++i) {
                    const ModelAdapterHealthInfo& adapter = model_registry_audit_.adapter_health[static_cast<size_t>(i)];
                    const std::string adapter_status = adapter.status.empty() ? "unknown" : adapter.status;
                    const bool ready_adapter = adapter_status == "ready";
                    const bool blocked_adapter =
                        adapter_status == "missing_secret" ||
                        adapter_status == "missing_model" ||
                        adapter_status == "unsupported_api" ||
                        adapter_status == "unconfigured";
                    const bool muted_adapter = adapter_status == "disabled";
                    const ImVec4 adapter_color = ready_adapter
                        ? Rgba(38, 221, 123)
                        : (muted_adapter ? Rgba(151, 160, 171) : (blocked_adapter ? Rgba(248, 113, 113) : Rgba(205, 154, 82)));
                    std::string attempts = std::to_string(adapter.recent_successes) + " ok / " +
                        std::to_string(adapter.recent_failures) + " fail";
                    if (adapter.recent_skips > 0 || adapter.preflight_skips > 0) {
                        attempts += " / " + std::to_string(adapter.recent_skips + adapter.preflight_skips) + " skip";
                    }
                    if (adapter.recent_attempts == 0 && adapter.preflight_skips == 0) {
                        attempts = "-";
                    }
                    std::string secret = adapter.local ? "local" : "not required";
                    if (!adapter.secret_env.empty()) {
                        secret = Shorten(adapter.secret_env, 24) + (adapter.secret_present ? " set" : " missing");
                    }
                    std::string adapter_message = adapter.message;
                    if (adapter_message.empty()) {
                        adapter_message = adapter.recommendation;
                    }
                    if (adapter_message.empty()) {
                        adapter_message = adapter.latest_error;
                    }
                    if (adapter_message.empty()) {
                        adapter_message = adapter.error_code;
                    }
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    Pill(Shorten(adapter_status, 14).c_str(), adapter_color);
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(adapter.provider_label.empty() ? adapter.provider_id : adapter.provider_label, 28),
                        ready_adapter ? Rgba(38, 221, 123) : Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(adapter.api.empty() ? "-" : adapter.api, 18));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(Shorten(adapter.model.empty() ? (adapter.endpoint.empty() ? "-" : adapter.endpoint) : adapter.model, 30));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(attempts);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(secret);
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(adapter_message.empty() ? "-" : adapter_message, 88));
                }
                ImGui::EndTable();
            }
            for (const ModelAdapterHealthInfo& adapter : model_registry_audit_.adapter_health) {
                if (adapter.status != "ready" && !adapter.recommendation.empty()) {
                    TextMuted("- " + Shorten(adapter.recommendation, 132));
                    break;
                }
            }
        }
        if (!model_registry_audit_.tokenizer_diagnostics.empty()) {
            const auto tokenizer_status_color = [](const std::string& status) {
                const std::string lowered = Lower(status);
                if (lowered == "exact" || lowered == "profiled") {
                    return Rgba(38, 221, 123);
                }
                if (lowered == "missing") {
                    return Rgba(248, 113, 113);
                }
                if (lowered == "heuristic" || lowered == "mixed") {
                    return Rgba(205, 154, 82);
                }
                return Rgba(151, 160, 171);
            };
            const auto calibration_status_color = [](const std::string& status) {
                const std::string lowered = Lower(status);
                if (lowered == "stable") {
                    return Rgba(38, 221, 123);
                }
                if (lowered == "watch") {
                    return Rgba(205, 154, 82);
                }
                if (lowered == "drift") {
                    return Rgba(248, 113, 113);
                }
                return Rgba(151, 160, 171);
            };

            int observed_count = 0;
            int exact_or_profiled_count = 0;
            int heuristic_or_missing_count = 0;
            int calibrated_count = 0;
            int calibration_attention_count = 0;
            for (const ModelTokenizerDiagnosticInfo& diagnostic : model_registry_audit_.tokenizer_diagnostics) {
                const std::string lowered = Lower(diagnostic.status);
                const std::string calibration_lowered = Lower(diagnostic.calibration_status);
                if (diagnostic.recent_attempts > 0) {
                    ++observed_count;
                }
                if (lowered == "exact" || lowered == "profiled") {
                    ++exact_or_profiled_count;
                }
                if (lowered == "missing" || lowered == "heuristic" || lowered == "mixed") {
                    ++heuristic_or_missing_count;
                }
                if (diagnostic.calibrated_attempts > 0) {
                    ++calibrated_count;
                }
                if (calibration_lowered == "watch" || calibration_lowered == "drift") {
                    ++calibration_attention_count;
                }
            }

            ImGui::Dummy(ImVec2(0.0f, 4.0f));
            TextColor("Tokenizer Diagnostics", Rgba(246, 248, 251));
            ImGui::Columns(5, "model_registry_tokenizer_summary", false);
            TextMuted("Observed");
            TextColor(std::to_string(observed_count), Rgba(246, 248, 251));
            ImGui::NextColumn();
            TextMuted("Profiled/Exact");
            TextColor(std::to_string(exact_or_profiled_count), exact_or_profiled_count > 0 ? Rgba(38, 221, 123) : Rgba(151, 160, 171));
            ImGui::NextColumn();
            TextMuted("Needs Work");
            TextColor(std::to_string(heuristic_or_missing_count), heuristic_or_missing_count > 0 ? Rgba(205, 154, 82) : Rgba(38, 221, 123));
            ImGui::NextColumn();
            TextMuted("Calibrated");
            TextColor(std::to_string(calibrated_count), calibrated_count > 0 ? Rgba(38, 221, 123) : Rgba(151, 160, 171));
            ImGui::NextColumn();
            TextMuted("Providers");
            TextColor(std::to_string(model_registry_audit_.tokenizer_diagnostics.size()), Rgba(246, 248, 251));
            ImGui::Columns(1);
            if (calibration_attention_count > 0) {
                TextColor(std::to_string(calibration_attention_count) + " provider(s) have token calibration drift or watch warnings.", Rgba(205, 154, 82));
            }
            const int diagnostic_count = std::min(8, static_cast<int>(model_registry_audit_.tokenizer_diagnostics.size()));
            if (ImGui::BeginTable("model_registry_tokenizer_diagnostics", 9, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 82.0f);
                ImGui::TableSetupColumn("Provider", ImGuiTableColumnFlags_WidthFixed, 130.0f);
                ImGui::TableSetupColumn("API", ImGuiTableColumnFlags_WidthFixed, 68.0f);
                ImGui::TableSetupColumn("Model", ImGuiTableColumnFlags_WidthFixed, 110.0f);
                ImGui::TableSetupColumn("Window", ImGuiTableColumnFlags_WidthFixed, 84.0f);
                ImGui::TableSetupColumn("Attempts", ImGuiTableColumnFlags_WidthFixed, 78.0f);
                ImGui::TableSetupColumn("Source", ImGuiTableColumnFlags_WidthFixed, 114.0f);
                ImGui::TableSetupColumn("Calib", ImGuiTableColumnFlags_WidthFixed, 94.0f);
                ImGui::TableSetupColumn("Recommendation");
                ImGui::TableHeadersRow();
                for (int i = 0; i < diagnostic_count; ++i) {
                    const ModelTokenizerDiagnosticInfo& diagnostic = model_registry_audit_.tokenizer_diagnostics[static_cast<size_t>(i)];
                    const std::string provider = diagnostic.provider_label.empty() ? diagnostic.provider_id : diagnostic.provider_label;
                    std::string window = diagnostic.has_context_window ? std::to_string(diagnostic.context_window) : "-";
                    if (diagnostic.has_average_context_utilization) {
                        window += " / " + FormatPercent(diagnostic.average_context_utilization);
                    }
                    const std::string attempts =
                        std::to_string(diagnostic.recent_attempts) +
                        " (" + std::to_string(diagnostic.exact_attempts) +
                        "/" + std::to_string(diagnostic.profiled_attempts) +
                        "/" + std::to_string(diagnostic.heuristic_attempts) +
                        "/" + std::to_string(diagnostic.missing_attempts) + ")";
                    const std::string source = diagnostic.primary_estimator_source.empty()
                        ? (diagnostic.estimator_sources.empty() ? "-" : diagnostic.estimator_sources.front())
                        : diagnostic.primary_estimator_source;
                    std::string calibration = diagnostic.calibration_status.empty() ? "insufficient" : diagnostic.calibration_status;
                    if (diagnostic.calibrated_attempts > 0) {
                        calibration += " " + std::to_string(diagnostic.calibrated_attempts);
                        if (diagnostic.has_average_input_token_error || diagnostic.has_average_output_token_error) {
                            calibration += " ";
                            calibration += diagnostic.has_average_input_token_error ? FormatPercent(diagnostic.average_input_token_error) : "-";
                            calibration += "/";
                            calibration += diagnostic.has_average_output_token_error ? FormatPercent(diagnostic.average_output_token_error) : "-";
                        }
                    }
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    Pill(Shorten(diagnostic.status.empty() ? "unknown" : diagnostic.status, 12).c_str(), tokenizer_status_color(diagnostic.status));
                    ImGui::TableSetColumnIndex(1);
                    TextColor(Shorten(provider.empty() ? "-" : provider, 28), Rgba(246, 248, 251));
                    ImGui::TableSetColumnIndex(2);
                    TextMuted(Shorten(diagnostic.api.empty() ? "-" : diagnostic.api, 18));
                    ImGui::TableSetColumnIndex(3);
                    TextMuted(Shorten(diagnostic.model.empty() ? "-" : diagnostic.model, 28));
                    ImGui::TableSetColumnIndex(4);
                    TextMuted(window);
                    ImGui::TableSetColumnIndex(5);
                    TextMuted(attempts);
                    ImGui::TableSetColumnIndex(6);
                    TextMuted(Shorten(source, 28));
                    ImGui::TableSetColumnIndex(7);
                    TextColor(Shorten(calibration, 24), calibration_status_color(diagnostic.calibration_status));
                    if (ImGui::IsItemHovered()) {
                        std::string tooltip = diagnostic.calibration_recommendation.empty() ? "Provider has not reported token usage yet." : diagnostic.calibration_recommendation;
                        if (!diagnostic.reported_token_sources.empty()) {
                            tooltip += "\nSources: " + JoinList(diagnostic.reported_token_sources);
                        }
                        ImGui::SetTooltip("%s", tooltip.c_str());
                    }
                    ImGui::TableSetColumnIndex(8);
                    TextMuted(Shorten(diagnostic.recommendation.empty() ? "-" : diagnostic.recommendation, 82));
                }
                ImGui::EndTable();
            }
            if (model_registry_audit_.tokenizer_diagnostics.size() > static_cast<size_t>(diagnostic_count)) {
                TextMuted("Showing " + std::to_string(diagnostic_count) + " of " + std::to_string(model_registry_audit_.tokenizer_diagnostics.size()) + " tokenizer diagnostics.");
            }
        }
        if (!model_registry_audit_.issues.empty()) {
            const int issue_count = std::min(3, static_cast<int>(model_registry_audit_.issues.size()));
            for (int i = 0; i < issue_count; ++i) {
                const ModelRegistryAuditIssueInfo& issue = model_registry_audit_.issues[static_cast<size_t>(i)];
                const bool error = issue.severity == "error";
                TextColor("- " + Shorten(issue.message, 126), error ? Rgba(248, 113, 113) : Rgba(205, 154, 82));
            }
        } else if (!model_registry_audit_.recommendations.empty()) {
            TextMuted("- " + Shorten(model_registry_audit_.recommendations.front(), 132));
        }
    } else {
        TextMuted("Refresh Model Manager to audit route coverage and provider configuration.");
    }

    ImGui::Dummy(ImVec2(0.0f, 6.0f));
    TextColor("Provider Blueprints", Rgba(246, 248, 251));
    TextMuted("Stage common local and cloud providers without storing secrets in the desktop app.");
    const ProviderBlueprint& selected_blueprint = ModelProviderBlueprintAt(selected_provider_blueprint_index_);
    if (ImGui::BeginCombo("Blueprint", selected_blueprint.label)) {
        for (int i = 0; i < ProviderBlueprintCount(); ++i) {
            const ProviderBlueprint& blueprint = ModelProviderBlueprintAt(i);
            const bool selected = selected_provider_blueprint_index_ == i;
            if (ImGui::Selectable(blueprint.label, selected)) {
                selected_provider_blueprint_index_ = i;
            }
            if (selected) {
                ImGui::SetItemDefaultFocus();
            }
        }
        ImGui::EndCombo();
    }
    if (ImGui::BeginTable("provider_blueprint_preview", 5, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_SizingStretchProp)) {
        ImGui::TableSetupColumn("API", ImGuiTableColumnFlags_WidthFixed, 122.0f);
        ImGui::TableSetupColumn("Target", ImGuiTableColumnFlags_WidthFixed, 78.0f);
        ImGui::TableSetupColumn("Secret", ImGuiTableColumnFlags_WidthFixed, 150.0f);
        ImGui::TableSetupColumn("Roles");
        ImGui::TableSetupColumn("Model Hint", ImGuiTableColumnFlags_WidthFixed, 168.0f);
        ImGui::TableHeadersRow();
        ImGui::TableNextRow();
        ImGui::TableSetColumnIndex(0);
        TextMuted(selected_blueprint.api);
        ImGui::TableSetColumnIndex(1);
        Pill(selected_blueprint.local ? "Local" : "Cloud", selected_blueprint.local ? Rgba(38, 221, 123) : Rgba(205, 154, 82));
        ImGui::TableSetColumnIndex(2);
        TextMuted(selected_blueprint.env_var[0] == '\0' ? "none" : selected_blueprint.env_var);
        ImGui::TableSetColumnIndex(3);
        TextMuted(Shorten(selected_blueprint.roles, 70));
        ImGui::TableSetColumnIndex(4);
        TextMuted(Shorten(selected_blueprint.default_model, 34));
        ImGui::EndTable();
    }
    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Stage Blueprint")) {
        HydrateModelProviderBlueprint(selected_provider_blueprint_index_);
    }
    ImGui::SameLine();
    if (ImGui::Button("Stage Model Target")) {
        SetBuffer(model_api_buffer_, selected_blueprint.api);
        SetBuffer(model_endpoint_buffer_, selected_blueprint.endpoint);
        const std::string model_hint = selected_blueprint.default_model;
        if (!model_hint.empty() &&
            model_hint.find("Configure") == std::string::npos &&
            model_hint.find("Pick") == std::string::npos) {
            SetBuffer(model_name_buffer_, model_hint);
        }
        status_ = "Staged model target from " + std::string(selected_blueprint.label) + ". Save Aegis Settings to persist it.";
        PushToast("Model target staged", selected_blueprint.label, "info");
    }
    ImGui::SameLine();
    if (ImGui::Button("Copy Setup Notes")) {
        ImGui::SetClipboardText(ProviderBlueprintSetupText(selected_blueprint).c_str());
        status_ = "Copied provider setup notes.";
    }
    ImGui::SameLine();
    ImGui::BeginDisabled(selected_blueprint.env_var[0] == '\0');
    if (ImGui::Button("Copy Env Name")) {
        ImGui::SetClipboardText(selected_blueprint.env_var);
        status_ = "Copied provider environment variable name.";
    }
    ImGui::EndDisabled();
    ImGui::EndDisabled();
    ImGui::Dummy(ImVec2(0.0f, 6.0f));

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
        ImGui::TableSetupColumn("Model", ImGuiTableColumnFlags_WidthFixed, 150.0f);
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
            TextMuted(provider.model_name.empty() ? (provider.local ? "local target" : "cloud target") : Shorten(provider.model_name, 28));
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
        ImGui::InputText("Model", provider_model_buffer_.data(), provider_model_buffer_.size());
        ImGui::InputText("Aliases", provider_aliases_buffer_.data(), provider_aliases_buffer_.size());
        ImGui::NextColumn();
        ImGui::InputText("Endpoint", provider_endpoint_buffer_.data(), provider_endpoint_buffer_.size());
        ImGui::InputText("Secret Env", provider_secret_env_buffer_.data(), provider_secret_env_buffer_.size());
        ImGui::InputText("Cost Tier", provider_cost_tier_buffer_.data(), provider_cost_tier_buffer_.size());
        ImGui::InputText("Health", provider_health_buffer_.data(), provider_health_buffer_.size());
        ImGui::Checkbox("Local provider", &model_provider_local_);
        ImGui::SameLine();
        ImGui::Checkbox("Enabled", &model_provider_enabled_);
        ImGui::SameLine();
        ImGui::Checkbox("Configured", &model_provider_configured_);
        ImGui::Columns(1);
        ImGui::Columns(4, "model_provider_limits_columns", false);
        ImGui::InputInt("Context", &model_provider_context_window_, 0, 0);
        ImGui::NextColumn();
        ImGui::InputInt("RPM", &model_provider_rate_limit_rpm_, 0, 0);
        ImGui::NextColumn();
        ImGui::InputFloat("Input / 1M", &model_provider_input_cost_per_million_, 0.0f, 0.0f, "%.4f");
        ImGui::NextColumn();
        ImGui::InputFloat("Output / 1M", &model_provider_output_cost_per_million_, 0.0f, 0.0f, "%.4f");
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
        "Done: add editable model registry CRUD plus provider blueprints for local and cloud providers.",
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
        RefreshRuntime(true);
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
                "Done: provider blueprints stage OpenAI, Claude, local, research, router, and judge lanes.",
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
                "Done: desktop registry editor with provider blueprint staging.",
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
    const bool can_repair_verify_chain =
        has_verification_result_ &&
        verification_result_.has_first_failure &&
        !ValidationPassed(verification_result_.first_failure) &&
        !busy_;

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
    command("export_verification_report", IconGlyph::Document, "Export Verification Report", "Save the latest Full Verify result and repair activity as Markdown.", has_verification_result_, [this]() {
        ExportVerificationReport();
    });
    command("open_verification_reports", IconGlyph::Documents, "Open Verification Reports", "Open the local folder for exported Full Verify reports.", true, [this]() {
        OpenVerificationReportsFolder();
    });
    command("attach_latest_verification_report", IconGlyph::Attach, "Attach Latest Verification Report", "Attach the newest exported Full Verify report to the next chat message.", !RecentVerificationReportPaths(1).empty(), [this]() {
        const std::vector<std::filesystem::path> reports = RecentVerificationReportPaths(1);
        if (!reports.empty()) {
            AttachVerificationReport(WideToUtf8(reports.front().wstring()));
        }
    });
    command("prune_verification_reports", IconGlyph::Tools, "Prune Verification Reports", "Keep the latest 25 Full Verify reports and delete older Markdown reports.", true, [this]() {
        PruneVerificationReports(25);
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
    command("repair_verify_until_clean", IconGlyph::Shield, "Repair Verify Until Clean", "Repair Full Verify failures one at a time, rerunning the full pipeline after each targeted fix.", can_repair_verify_chain, [this]() {
        RepairLastValidationFailure(true);
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
    command("planning_history", IconGlyph::History, "Planning History", "Inspect recent context budgets, model attempts, costs, and routing decisions.", !busy_, [this]() {
        RefreshTelemetry();
        pending_popup_ = "Aegis Planning History";
        status_ = "Opened planning history.";
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
    command("project_builder", IconGlyph::Plus, "New Project Builder", "Create a full starter project from a checkpointed scaffold preset.", true, [this]() {
        HydrateProjectBuilderDefaults();
        if (!project_scaffold_presets_loaded_ && !busy_) {
            RefreshProjectBuilderPresets();
        }
        pending_popup_ = "Aegis Project Builder";
        status_ = "Opened project builder.";
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
    command("full_verify", IconGlyph::Shield, "Full Verify", "Run the ordered install, configure, build, type-check, lint, database, and test pipeline.", !busy_, [this]() {
        VerifyWorkspace();
    });
    command("refresh", IconGlyph::Sparkle, "Refresh Runtime", "Reload backend health, workspace files, history, and model inventory.", !busy_, [this]() {
        RefreshRuntime(true);
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
    ImGui::Dummy(ImVec2(0.0f, 8.0f));
    if (RowButton("route_project_builder", IconGlyph::Plus, "New Project Builder", "Scaffold a full starter project with checkpoint and validation profile")) {
        HydrateProjectBuilderDefaults();
        if (!project_scaffold_presets_loaded_ && !busy_) {
            RefreshProjectBuilderPresets();
        }
        pending_popup_ = "Aegis Project Builder";
        ImGui::CloseCurrentPopup();
    }

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

void AegisChatApp::RenderProjectBuilderModal()
{
    const bool planned_existing_validation =
        project_scaffold_has_plan_ && IsExistingProjectValidationMode(project_scaffold_plan_);
    TextColor(planned_existing_validation ? "Existing Project Builder" : "Project Builder", Rgba(246, 248, 251));
    TextMuted(planned_existing_validation
        ? "Validate, build, and repair an existing workspace without generating starter files."
        : "Create a full starter project from a deterministic preset, checkpoint every generated file, and save a validation command for the workspace.");
    ImGui::Dummy(ImVec2(0.0f, 8.0f));

    if (!project_scaffold_presets_loaded_ && !project_scaffold_presets_requested_ && !busy_) {
        RefreshProjectBuilderPresets();
    }

    ImGui::BeginDisabled(busy_);
    if (ImGui::Button("Refresh Presets")) {
        RefreshProjectBuilderPresets();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    TextMuted(project_scaffold_presets_loaded_
        ? "Presets loaded."
        : (busy_ ? "Loading or waiting for backend..." : "Presets not loaded yet."));

    HydrateProjectBuilderDefaults();
    ImGui::Separator();

    ImGui::TextUnformatted("Project prompt");
    ImGui::SetNextItemWidth(-1.0f);
    ImGui::InputTextMultiline(
        "##project_builder_prompt",
        project_scaffold_prompt_buffer_.data(),
        project_scaffold_prompt_buffer_.size(),
        ImVec2(-1.0f, 74.0f));
    ImGui::BeginDisabled(busy_);
    if (IconTextButton("project_builder_plan_prompt", IconGlyph::Sparkle, "Plan + Preview", ImVec2(170.0f, 38.0f), Rgba(20, 98, 62), Rgba(22, 130, 76), Rgba(246, 248, 251))) {
        PlanProjectFromPrompt();
    }
    ImGui::EndDisabled();
    ImGui::SameLine();
    TextMuted(project_scaffold_has_plan_
        ? ("Last plan: " + project_scaffold_plan_.preset.label + " (" + std::to_string(static_cast<int>(project_scaffold_plan_.confidence * 100.0)) + "%)")
        : "Use the composer text or this prompt box.");
    ImGui::Separator();

    if (project_scaffold_presets_.empty()) {
        TextMuted("No presets are available yet. Check that the backend is running and refresh presets.");
    } else {
        selected_project_scaffold_preset_index_ = std::clamp(
            selected_project_scaffold_preset_index_,
            0,
            static_cast<int>(project_scaffold_presets_.size()) - 1);
        const ProjectScaffoldPresetInfo& selected_preset =
            project_scaffold_presets_[static_cast<size_t>(selected_project_scaffold_preset_index_)];
        const std::string current_label = selected_preset.label.empty() ? selected_preset.id : selected_preset.label;

        ImGui::TextUnformatted("Preset");
        ImGui::SetNextItemWidth(-1.0f);
        if (ImGui::BeginCombo("##project_builder_preset", current_label.c_str())) {
            for (int i = 0; i < static_cast<int>(project_scaffold_presets_.size()); ++i) {
                const ProjectScaffoldPresetInfo& preset = project_scaffold_presets_[static_cast<size_t>(i)];
                const std::string label = preset.label.empty() ? preset.id : preset.label;
                const bool selected = i == selected_project_scaffold_preset_index_;
                if (ImGui::Selectable(label.c_str(), selected)) {
                    selected_project_scaffold_preset_index_ = i;
                    SetBuffer(project_scaffold_install_buffer_, preset.install_command);
                    SetBuffer(project_scaffold_validation_buffer_, preset.validation_command);
                }
                if (selected) {
                    ImGui::SetItemDefaultFocus();
                }
            }
            ImGui::EndCombo();
        }

        TextMuted(selected_preset.description.empty() ? "No preset description." : selected_preset.description);
        ImGui::Dummy(ImVec2(0.0f, 8.0f));

        if (project_scaffold_has_plan_) {
            TextColor("Prompt Plan", Rgba(246, 248, 251));
            TextMuted("Mode: " + ProjectBuilderModeText(planned_existing_validation));
            TextMuted(project_scaffold_plan_.message.empty() ? "Project plan ready." : project_scaffold_plan_.message);
            if (!project_scaffold_plan_.detected_keywords.empty()) {
                TextMuted("Matched: " + JoinList(project_scaffold_plan_.detected_keywords, ", "));
            }
            for (const std::string& reason : project_scaffold_plan_.reasons) {
                ImGui::BulletText("%s", reason.c_str());
            }
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
        }

        ImGui::Columns(2, "project_builder_inputs", false);
        ImGui::SetColumnWidth(0, 430.0f);
        ImGui::TextUnformatted("Project name");
        ImGui::SetNextItemWidth(-1.0f);
        ImGui::InputText("##project_builder_name", project_scaffold_name_buffer_.data(), project_scaffold_name_buffer_.size());
        TextMuted("Used for package metadata and generated titles.");

        ImGui::NextColumn();
        ImGui::TextUnformatted("Target folder");
        ImGui::SetNextItemWidth(-1.0f);
        ImGui::InputText("##project_builder_target", project_scaffold_target_buffer_.data(), project_scaffold_target_buffer_.size());
        TextMuted("Absolute project paths are allowed; drive roots and protected system folders are rejected.");
        ImGui::Columns(1);

        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        ImGui::Columns(2, "project_builder_commands", false);
        ImGui::SetColumnWidth(0, 430.0f);
        ImGui::TextUnformatted("Install command");
        ImGui::SetNextItemWidth(-1.0f);
        ImGui::InputText("##project_builder_install", project_scaffold_install_buffer_.data(), project_scaffold_install_buffer_.size());
        TextMuted("Saved as a next step; Aegis will not run it automatically.");

        ImGui::NextColumn();
        ImGui::TextUnformatted("Validation command");
        ImGui::SetNextItemWidth(-1.0f);
        ImGui::InputText("##project_builder_validation", project_scaffold_validation_buffer_.data(), project_scaffold_validation_buffer_.size());
        TextMuted(planned_existing_validation
            ? "Used for this existing-project validation/build pass."
            : "Saved into the workspace validation profile.");
        ImGui::Columns(1);

        ImGui::Dummy(ImVec2(0.0f, 8.0f));
        ImGui::Checkbox("Include .gitignore", &project_scaffold_include_gitignore_);
        ImGui::SameLine();
        ImGui::Checkbox("Overwrite scaffold-owned files", &project_scaffold_overwrite_);
        ImGui::SameLine();
        ImGui::Checkbox("Run validation after create", &project_scaffold_run_validation_);
        ImGui::SameLine();
        ImGui::Checkbox("Run install first", &project_scaffold_run_install_);
        TextMuted(planned_existing_validation
            ? "Validation-only passes do not generate starter files. Overwrite only affects later scaffold-owned updates."
            : (project_scaffold_overwrite_
                ? "Existing files generated by the selected preset can be updated. Other files are left alone."
                : "Non-empty target folders are blocked until overwrite is enabled."));
        TextMuted(project_scaffold_run_validation_
            ? (planned_existing_validation
                ? "Run Validation will attempt the build command and capture stdout/stderr for repair."
                : "Create will attempt the validation/build command and capture stdout/stderr for repair.")
            : (planned_existing_validation
                ? "Run Validation will save the command for later; no build command will run immediately."
                : "Create will save validation for later; no build command will run immediately."));

        ImGui::Dummy(ImVec2(0.0f, 10.0f));
        ImGui::BeginDisabled(busy_ || BufferString(project_scaffold_target_buffer_.data()).empty());
        const std::string preview_button_label = planned_existing_validation ? "Preview Validate" : "Preview Plan";
        if (IconTextButton("project_builder_preview", IconGlyph::Document, preview_button_label.c_str(), ImVec2(164.0f, 38.0f), Rgba(17, 25, 34), Rgba(25, 35, 47), Rgba(246, 248, 251))) {
            PreviewProjectFromBuilder();
        }
        ImGui::SameLine();
        const std::string create_button_label = planned_existing_validation ? "Run Validation" : "Create Project";
        if (IconTextButton("project_builder_create", IconGlyph::Plus, create_button_label.c_str(), ImVec2(170.0f, 38.0f), Rgba(20, 98, 62), Rgba(22, 130, 76), Rgba(246, 248, 251))) {
            ScaffoldProjectFromBuilder();
        }
        ImGui::EndDisabled();
    }

    if (project_scaffold_has_result_) {
        ImGui::Separator();
        const bool result_existing_validation = IsExistingProjectValidationMode(project_scaffold_result_);
        const std::string result_heading = !project_scaffold_result_.ok
            ? (result_existing_validation ? "Validation Issue" : "Scaffold Issue")
            : (result_existing_validation
                ? (project_scaffold_result_preview_ ? "Validation Preview" : "Validation Result")
                : (project_scaffold_result_preview_ ? "Scaffold Preview" : "Scaffold Result"));
        TextColor(
            result_heading,
            project_scaffold_result_.ok ? Rgba(38, 221, 123) : Rgba(239, 115, 115));
        TextMuted("Mode: " + ProjectBuilderModeText(result_existing_validation));
        TextMuted(project_scaffold_result_.message.empty() ? "Project builder returned a result." : project_scaffold_result_.message);
        TextMuted("Target: " + Shorten(project_scaffold_result_.target_path, 120));
        if (result_existing_validation && project_scaffold_result_.files.empty()) {
            TextMuted("No starter files were generated for this validation-only pass.");
        }
        if (!project_scaffold_result_.diff_summary.empty()) {
            TextMuted("Diff: " + JoinList(project_scaffold_result_.diff_summary, ", "));
        }
        if (!project_scaffold_result_.checkpoint.empty()) {
            TextMuted("Checkpoint: " + project_scaffold_result_.checkpoint);
        } else if (project_scaffold_result_preview_) {
            TextMuted("Preview only: no files have been written yet.");
        }

        ImGui::BeginDisabled(project_scaffold_result_preview_ || !project_scaffold_result_.ok || project_scaffold_result_.target_path.empty());
        if (ImGui::Button("Use As Workspace")) {
            UseScaffoldedProjectAsWorkspace();
        }
        ImGui::EndDisabled();
        ImGui::SameLine();
        if (!project_scaffold_result_.target_path.empty() && ImGui::Button("Open Folder")) {
            OpenExternalPath(std::filesystem::path(Utf8ToWide(project_scaffold_result_.target_path)));
        }

        if (!project_scaffold_result_.warnings.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextColor("Warnings", Rgba(239, 115, 115));
            for (const std::string& warning : project_scaffold_result_.warnings) {
                ImGui::BulletText("%s", warning.c_str());
            }
        }
        if (!project_scaffold_result_.risk_warnings.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 6.0f));
            TextColor("Risk Notes", Rgba(248, 196, 87));
            for (const std::string& warning : project_scaffold_result_.risk_warnings) {
                ImGui::BulletText("%s", warning.c_str());
            }
        }

        if (!project_scaffold_result_.stages.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Build Loop", Rgba(246, 248, 251));
            if (ImGui::BeginTable("project_builder_stages", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_NoSavedSettings)) {
                ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 92.0f);
                ImGui::TableSetupColumn("Stage", ImGuiTableColumnFlags_WidthFixed, 190.0f);
                ImGui::TableSetupColumn("Command", ImGuiTableColumnFlags_WidthFixed, 220.0f);
                ImGui::TableSetupColumn("Detail");
                ImGui::TableHeadersRow();
                for (const ProjectBuildStageInfo& stage : project_scaffold_result_.stages) {
                    ImGui::TableNextRow();
                    ImGui::TableSetColumnIndex(0);
                    const ImVec4 status_color =
                        stage.status == "succeeded" ? Rgba(38, 221, 123) :
                        (stage.status == "failed" || stage.status == "blocked") ? Rgba(239, 115, 115) :
                        stage.status == "skipped" ? Rgba(148, 163, 184) :
                        Rgba(248, 196, 87);
                    TextColor(stage.status.empty() ? "planned" : stage.status, status_color);
                    ImGui::TableSetColumnIndex(1);
                    ImGui::TextWrapped("%s", stage.label.c_str());
                    ImGui::TableSetColumnIndex(2);
                    ImGui::TextWrapped("%s", stage.command.empty() ? "-" : stage.command.c_str());
                    ImGui::TableSetColumnIndex(3);
                    ImGui::TextWrapped("%s", stage.detail.empty() ? "-" : stage.detail.c_str());
                    if (!stage.output_excerpt.empty()) {
                        ImGui::TextWrapped("%s", Shorten(stage.output_excerpt, 260).c_str());
                    }
                }
                ImGui::EndTable();
            }
        }

        if (!project_scaffold_result_.roadmap_path.empty()) {
            TextMuted("Roadmap: " + project_scaffold_result_.roadmap_path);
        }

        if (project_scaffold_result_.has_validation) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            const bool passed = ValidationPassed(project_scaffold_result_.validation);
            TextColor(passed ? "Validation passed" : "Validation captured", passed ? Rgba(38, 221, 123) : Rgba(239, 115, 115));
            TextMuted(project_scaffold_result_.validation.summary.empty()
                ? project_scaffold_result_.validation.reason
                : project_scaffold_result_.validation.summary);
            if (!project_scaffold_result_.validation.command.empty()) {
                TextMuted("Command: " + project_scaffold_result_.validation.command);
            }
            const std::string validation_output = Shorten(ValidationCombinedOutput(project_scaffold_result_.validation), 2400);
            if (!validation_output.empty()) {
                ImGui::BeginChild("project_builder_validation_console", ImVec2(0, 150.0f), true, ImGuiWindowFlags_HorizontalScrollbar);
                ImGui::TextUnformatted(validation_output.c_str());
                ImGui::EndChild();
            }
        }

        if (project_scaffold_result_.files.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextMuted(result_existing_validation
                ? "Files changed: 0. This pass focused on build/validation output."
                : "No file preview was returned for this pass.");
        } else if (ImGui::BeginTable("project_builder_files", 4, ImGuiTableFlags_BordersInnerH | ImGuiTableFlags_RowBg | ImGuiTableFlags_NoSavedSettings)) {
            ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthFixed, 82.0f);
            ImGui::TableSetupColumn("File");
            ImGui::TableSetupColumn("Size", ImGuiTableColumnFlags_WidthFixed, 80.0f);
            ImGui::TableSetupColumn("Summary");
            ImGui::TableHeadersRow();
            for (const ProjectScaffoldFileInfo& file : project_scaffold_result_.files) {
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::TextUnformatted(file.action.c_str());
                ImGui::TableSetColumnIndex(1);
                ImGui::TextUnformatted(file.path.c_str());
                ImGui::TableSetColumnIndex(2);
                ImGui::Text("%lld", file.size);
                ImGui::TableSetColumnIndex(3);
                ImGui::TextWrapped("%s", file.summary.c_str());
            }
            ImGui::EndTable();
        }

        if (!project_scaffold_result_.next_steps.empty()) {
            ImGui::Dummy(ImVec2(0.0f, 8.0f));
            TextColor("Next Steps", Rgba(246, 248, 251));
            for (const std::string& step : project_scaffold_result_.next_steps) {
                ImGui::BulletText("%s", step.c_str());
            }
        }
    }
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
