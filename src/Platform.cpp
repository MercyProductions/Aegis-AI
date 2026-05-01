#include "Platform.h"

#include "Json.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <d3d11.h>
#include <mmsystem.h>
#include <winhttp.h>
#include <shellapi.h>
#include <shlobj.h>
#include <wincodec.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <thread>

namespace aegis {
namespace {

HWND g_host_window = nullptr;
ID3D11Device* g_d3d_device = nullptr;
const wchar_t* kAudioPreviewAlias = L"aegis_audio_preview";

template <typename T>
void ReleaseCom(T*& ptr)
{
    if (ptr != nullptr) {
        ptr->Release();
        ptr = nullptr;
    }
}

void SetError(std::string* error, const std::string& message)
{
    if (error != nullptr) {
        *error = message;
    }
}

std::string MciErrorMessage(MCIERROR code)
{
    std::array<wchar_t, 512> buffer{};
    if (mciGetErrorStringW(code, buffer.data(), static_cast<UINT>(buffer.size()))) {
        return WideToUtf8(buffer.data());
    }
    return "Windows media playback failed.";
}

std::wstring MciDeviceTypeForPath(const std::filesystem::path& path)
{
    const std::string extension = Lower(WideToUtf8(path.extension().wstring()));
    if (extension == ".wav") {
        return L"waveaudio";
    }
    if (extension == ".mp3" || extension == ".mp4" || extension == ".m4a" || extension == ".aac" || extension == ".wma") {
        return L"mpegvideo";
    }
    if (extension == ".mid" || extension == ".midi") {
        return L"sequencer";
    }
    return {};
}

MCIERROR SendMciCommand(const std::wstring& command)
{
    return mciSendStringW(command.c_str(), nullptr, 0, nullptr);
}

std::vector<std::string> SplitLines(const std::string& value)
{
    std::vector<std::string> lines;
    std::stringstream stream(value);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        lines.push_back(line);
    }
    return lines;
}

std::filesystem::path ConfigPath()
{
    return ProjectDirectoryFromExecutable() / "AegisChatBot.config.ini";
}

bool ParseBool(const std::string& value, bool fallback)
{
    const std::string lowered = Lower(Trim(value));
    if (lowered == "true" || lowered == "1" || lowered == "yes" || lowered == "on") {
        return true;
    }
    if (lowered == "false" || lowered == "0" || lowered == "no" || lowered == "off") {
        return false;
    }
    return fallback;
}

std::filesystem::path ResolveConfigPath(const std::filesystem::path& base, const std::string& value)
{
    if (Trim(value).empty()) {
        return {};
    }

    std::filesystem::path path = Utf8ToWide(Trim(value));
    if (path.is_absolute()) {
        return path.lexically_normal();
    }
    return (base / path).lexically_normal();
}

std::string PathToUtf8(const std::filesystem::path& path)
{
    return WideToUtf8(path.wstring());
}

HttpResponse SendWinHttpRequest(
    const std::wstring& method,
    const std::string& url,
    const std::string* body,
    const std::function<void(const std::string&)>& on_chunk = {},
    const std::wstring& accept = L"application/json")
{
    HttpResponse response;
    const std::wstring wide_url = Utf8ToWide(url);

    URL_COMPONENTS components{};
    components.dwStructSize = sizeof(components);
    components.dwSchemeLength = static_cast<DWORD>(-1);
    components.dwHostNameLength = static_cast<DWORD>(-1);
    components.dwUrlPathLength = static_cast<DWORD>(-1);
    components.dwExtraInfoLength = static_cast<DWORD>(-1);

    if (!WinHttpCrackUrl(wide_url.c_str(), 0, 0, &components)) {
        response.error = "Failed to parse URL.";
        return response;
    }

    const std::wstring host(components.lpszHostName, components.dwHostNameLength);
    std::wstring path(components.lpszUrlPath, components.dwUrlPathLength);
    if (components.dwExtraInfoLength > 0) {
        path.append(components.lpszExtraInfo, components.dwExtraInfoLength);
    }

    HINTERNET session = WinHttpOpen(
        L"AegisChatBotDesktop/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        0);
    if (!session) {
        response.error = "Failed to open HTTP session.";
        return response;
    }

    WinHttpSetTimeouts(session, 4000, 5000, 8000, 180000);

    HINTERNET connection = WinHttpConnect(session, host.c_str(), components.nPort, 0);
    if (!connection) {
        response.error = "Failed to connect to HTTP host.";
        WinHttpCloseHandle(session);
        return response;
    }

    const DWORD flags = components.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET request = WinHttpOpenRequest(
        connection,
        method.c_str(),
        path.c_str(),
        nullptr,
        WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES,
        flags);
    if (!request) {
        response.error = "Failed to create HTTP request.";
        WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return response;
    }

    std::wstring headers = L"Accept: " + accept + L"\r\n";
    if (body != nullptr) {
        headers += L"Content-Type: application/json; charset=utf-8\r\n";
    }

    const void* body_data = body == nullptr || body->empty() ? WINHTTP_NO_REQUEST_DATA : body->data();
    const DWORD body_size = body == nullptr ? 0u : static_cast<DWORD>(body->size());

    const BOOL sent = WinHttpSendRequest(
        request,
        headers.c_str(),
        static_cast<DWORD>(-1L),
        const_cast<void*>(body_data),
        body_size,
        body_size,
        0);

    if (!sent || !WinHttpReceiveResponse(request, nullptr)) {
        response.error = "HTTP request failed.";
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connection);
        WinHttpCloseHandle(session);
        return response;
    }

    DWORD status_code = 0;
    DWORD status_size = sizeof(status_code);
    WinHttpQueryHeaders(
        request,
        WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
        WINHTTP_HEADER_NAME_BY_INDEX,
        &status_code,
        &status_size,
        WINHTTP_NO_HEADER_INDEX);
    response.status_code = static_cast<int>(status_code);

    DWORD raw_size = 0;
    WinHttpQueryHeaders(
        request,
        WINHTTP_QUERY_RAW_HEADERS_CRLF,
        WINHTTP_HEADER_NAME_BY_INDEX,
        nullptr,
        &raw_size,
        WINHTTP_NO_HEADER_INDEX);
    if (GetLastError() == ERROR_INSUFFICIENT_BUFFER && raw_size > 0) {
        std::wstring raw(raw_size / sizeof(wchar_t), L'\0');
        if (WinHttpQueryHeaders(
                request,
                WINHTTP_QUERY_RAW_HEADERS_CRLF,
                WINHTTP_HEADER_NAME_BY_INDEX,
                raw.data(),
                &raw_size,
                WINHTTP_NO_HEADER_INDEX)) {
            raw.resize(raw_size / sizeof(wchar_t));
            response.raw_headers = WideToUtf8(raw);
        }
    }

    DWORD available = 0;
    while (WinHttpQueryDataAvailable(request, &available) && available > 0) {
        std::string chunk(static_cast<size_t>(available), '\0');
        DWORD downloaded = 0;
        if (!WinHttpReadData(request, chunk.data(), available, &downloaded) || downloaded == 0) {
            break;
        }
        chunk.resize(downloaded);
        response.body += chunk;
        if (on_chunk) {
            on_chunk(chunk);
        }
    }

    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connection);
    WinHttpCloseHandle(session);
    return response;
}

}

std::filesystem::path ExecutableDirectory()
{
    std::array<wchar_t, 32768> buffer{};
    const DWORD read = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (read == 0 || read >= buffer.size()) {
        return std::filesystem::current_path();
    }
    return std::filesystem::path(std::wstring(buffer.data(), read)).parent_path();
}

std::filesystem::path AppDataDirectory()
{
    PWSTR raw = nullptr;
    std::filesystem::path base;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &raw)) && raw != nullptr) {
        base = raw;
        CoTaskMemFree(raw);
    } else {
        base = ExecutableDirectory();
    }

    std::filesystem::path path = base / "Aegis" / "ChatBot";
    std::error_code ec;
    std::filesystem::create_directories(path, ec);
    return path;
}

std::filesystem::path ProjectDirectoryFromExecutable()
{
    const std::filesystem::path exe = ExecutableDirectory();
    std::filesystem::path cursor = exe;
    for (int i = 0; i < 8; ++i) {
        if (std::filesystem::exists(cursor / "imgui" / "imgui.h") &&
            std::filesystem::exists(cursor / "src")) {
            return cursor;
        }
        if (!cursor.has_parent_path() || cursor == cursor.parent_path()) {
            break;
        }
        cursor = cursor.parent_path();
    }
    return std::filesystem::current_path();
}

std::filesystem::path LocateDefaultBackendRoot()
{
    std::vector<std::filesystem::path> starts = {
        ProjectDirectoryFromExecutable(),
        ExecutableDirectory(),
        std::filesystem::current_path()
    };

    for (std::filesystem::path start : starts) {
        for (int i = 0; i < 10; ++i) {
            const std::filesystem::path candidate = start / "Website" / "ChatBot";
            if (std::filesystem::exists(candidate / "backend" / "aegis_ai" / "main.py")) {
                return candidate.lexically_normal();
            }
            if (!start.has_parent_path() || start == start.parent_path()) {
                break;
            }
            start = start.parent_path();
        }
    }

    return (ProjectDirectoryFromExecutable() / ".." / ".." / ".." / "Website" / "ChatBot").lexically_normal();
}

bool BackendRootLooksValid(const std::filesystem::path& root)
{
    return std::filesystem::exists(root / "backend" / "aegis_ai" / "main.py");
}

DesktopSettings LoadDesktopSettings()
{
    DesktopSettings settings;
    settings.backend_root = LocateDefaultBackendRoot();

    const std::filesystem::path config_path = ConfigPath();
    std::ifstream file(config_path);
    if (!file) {
        return settings;
    }

    const std::filesystem::path base = config_path.parent_path();
    std::string line;
    while (std::getline(file, line)) {
        line = Trim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';' || line[0] == '[') {
            continue;
        }

        const size_t eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }

        const std::string key = Lower(Trim(line.substr(0, eq)));
        const std::string value = Trim(line.substr(eq + 1));
        if (key == "api_base_url") {
            settings.api_base_url = value;
        } else if (key == "backend_root") {
            const std::filesystem::path configured_root = ResolveConfigPath(base, value);
            if (BackendRootLooksValid(configured_root)) {
                settings.backend_root = configured_root;
            }
        } else if (key == "backend_start_script") {
            settings.backend_start_script = value;
        } else if (key == "auto_start_backend") {
            settings.auto_start_backend = ParseBool(value, settings.auto_start_backend);
        } else if (key == "max_files") {
            settings.max_files = std::max(20, std::min(500, std::atoi(value.c_str())));
        }
    }

    settings.api_base_url = Trim(settings.api_base_url);
    while (!settings.api_base_url.empty() && settings.api_base_url.back() == '/') {
        settings.api_base_url.pop_back();
    }
    if (settings.api_base_url.empty()) {
        settings.api_base_url = "http://127.0.0.1:8787";
    }
    return settings;
}

bool SaveDesktopSettings(const DesktopSettings& settings, std::string& error)
{
    const std::filesystem::path path = ConfigPath();
    std::error_code ec;
    std::filesystem::create_directories(path.parent_path(), ec);

    std::ofstream file(path, std::ios::trunc);
    if (!file) {
        error = "Could not write desktop config.";
        return false;
    }

    file << "api_base_url=" << settings.api_base_url << "\n";
    file << "backend_root=" << PathToUtf8(settings.backend_root) << "\n";
    file << "backend_start_script=" << settings.backend_start_script << "\n";
    file << "auto_start_backend=" << (settings.auto_start_backend ? "true" : "false") << "\n";
    file << "max_files=" << settings.max_files << "\n";
    return true;
}

std::wstring Utf8ToWide(const std::string& value)
{
    if (value.empty()) {
        return {};
    }
    const int size = MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0);
    std::wstring wide(static_cast<size_t>(size), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), wide.data(), size);
    return wide;
}

std::string WideToUtf8(const std::wstring& value)
{
    if (value.empty()) {
        return {};
    }
    const int size = WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
    std::string utf8(static_cast<size_t>(size), '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), utf8.data(), size, nullptr, nullptr);
    return utf8;
}

std::string GetEnvUtf8(const wchar_t* name)
{
    std::array<wchar_t, 4096> buffer{};
    const DWORD read = GetEnvironmentVariableW(name, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (read == 0 || read >= buffer.size()) {
        return {};
    }
    return WideToUtf8(std::wstring(buffer.data(), read));
}

std::string Trim(const std::string& value)
{
    size_t first = 0;
    while (first < value.size() && std::isspace(static_cast<unsigned char>(value[first])) != 0) {
        ++first;
    }
    size_t last = value.size();
    while (last > first && std::isspace(static_cast<unsigned char>(value[last - 1])) != 0) {
        --last;
    }
    return value.substr(first, last - first);
}

std::string Lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return value;
}

std::string EscapeJson(const std::string& value)
{
    std::string out;
    out.reserve(value.size() + 8);
    for (const char c : value) {
        switch (c) {
        case '\\': out += "\\\\"; break;
        case '"': out += "\\\""; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default:
            if (static_cast<unsigned char>(c) < 0x20) {
                out += ' ';
            } else {
                out += c;
            }
            break;
        }
    }
    return out;
}

std::string UrlEncode(const std::string& value)
{
    std::ostringstream stream;
    stream << std::uppercase << std::hex << std::setfill('0');
    for (const unsigned char c : value) {
        if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
            c == '-' || c == '_' || c == '.' || c == '~') {
            stream << static_cast<char>(c);
        } else {
            stream << '%' << std::setw(2) << static_cast<int>(c);
        }
    }
    return stream.str();
}

std::string JoinUrl(const std::string& base, const std::string& path)
{
    if (path.rfind("http://", 0) == 0 || path.rfind("https://", 0) == 0) {
        return path;
    }
    if (base.empty()) {
        return path;
    }

    const bool base_slash = base.back() == '/';
    const bool path_slash = !path.empty() && path.front() == '/';
    if (base_slash && path_slash) {
        return base.substr(0, base.size() - 1) + path;
    }
    if (!base_slash && !path_slash) {
        return base + "/" + path;
    }
    return base + path;
}

std::string FormatBytes(long long size)
{
    std::ostringstream stream;
    if (size < 1024) {
        stream << size << " B";
    } else if (size < 1024 * 1024) {
        stream << std::fixed << std::setprecision(1) << (static_cast<double>(size) / 1024.0) << " KB";
    } else {
        stream << std::fixed << std::setprecision(1) << (static_cast<double>(size) / 1024.0 / 1024.0) << " MB";
    }
    return stream.str();
}

std::string NowTimeLabel()
{
    const auto now = std::chrono::system_clock::now();
    const std::time_t tt = std::chrono::system_clock::to_time_t(now);
    std::tm local{};
    localtime_s(&local, &tt);
    std::ostringstream stream;
    stream << std::put_time(&local, "%H:%M:%S");
    return stream.str();
}

std::string FirstJsonErrorDetail(const std::string& body)
{
    const JsonParseResult parsed = ParseJson(body);
    if (!parsed.ok || !parsed.value.IsObject()) {
        return {};
    }
    const JsonValue& detail = parsed.value["detail"];
    if (detail.IsString()) {
        return detail.AsString();
    }
    if (detail.IsArray() && !detail.array_value.empty()) {
        const JsonValue& first = detail.At(0);
        if (first.IsString()) {
            return first.AsString();
        }
        if (first.IsObject()) {
            return first["msg"].AsString();
        }
    }
    return {};
}

HttpResponse HttpGet(const std::string& url)
{
    return SendWinHttpRequest(L"GET", url, nullptr);
}

HttpResponse HttpPostJson(const std::string& url, const std::string& body)
{
    return SendWinHttpRequest(L"POST", url, &body);
}

HttpResponse HttpPostJsonStream(
    const std::string& url,
    const std::string& body,
    const std::function<void(const std::string&)>& on_chunk)
{
    return SendWinHttpRequest(L"POST", url, &body, on_chunk, L"text/event-stream");
}

HttpResponse HttpPutJson(const std::string& url, const std::string& body)
{
    return SendWinHttpRequest(L"PUT", url, &body);
}

HttpResponse HttpDelete(const std::string& url)
{
    return SendWinHttpRequest(L"DELETE", url, nullptr);
}

bool BackendHealthEndpointReady(const DesktopSettings& settings)
{
    try {
        const HttpResponse response = HttpGet(JoinUrl(settings.api_base_url, "/api/health"));
        return response.status_code >= 200 && response.status_code < 300 && response.error.empty();
    } catch (...) {
        return false;
    }
}

bool StartBackendProcess(const DesktopSettings& settings, std::string& error)
{
    if (BackendHealthEndpointReady(settings)) {
        return true;
    }

    const std::filesystem::path root = settings.backend_root;
    const std::filesystem::path python = root / ".venv" / "Scripts" / "python.exe";
    const std::filesystem::path backend = root / "backend";

    std::wstring command;
    if (std::filesystem::exists(python) && std::filesystem::exists(backend / "aegis_ai" / "main.py")) {
        command = L"\"";
        command += python.wstring();
        command += L"\" -m uvicorn aegis_ai.main:app --app-dir \"";
        command += backend.wstring();
        command += L"\" --host 127.0.0.1 --port 8787";
    } else {
        const std::filesystem::path script = root / Utf8ToWide(settings.backend_start_script);
        if (!std::filesystem::exists(script)) {
            error = "Backend venv and fallback start script were not found.";
            return false;
        }

        std::filesystem::path powershell = std::filesystem::path(GetEnvUtf8(L"WINDIR")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe";
        if (!std::filesystem::exists(powershell)) {
            powershell = L"powershell.exe";
        }

        command = L"\"";
        command += powershell.wstring();
        command += L"\" -NoProfile -ExecutionPolicy Bypass -File \"";
        command += script.wstring();
        command += L"\"";
    }

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION process{};
    std::wstring mutable_command = command;
    const BOOL ok = CreateProcessW(
        nullptr,
        mutable_command.data(),
        nullptr,
        nullptr,
        FALSE,
        CREATE_NO_WINDOW,
        nullptr,
        root.wstring().c_str(),
        &startup,
        &process);

    if (!ok) {
        error = "Could not launch backend process.";
        return false;
    }

    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    std::this_thread::sleep_for(std::chrono::milliseconds(1800));
    return true;
}

void OpenExternalPath(const std::filesystem::path& path)
{
    ShellExecuteW(nullptr, L"open", path.wstring().c_str(), nullptr, nullptr, SW_SHOWNORMAL);
}

void SetHostWindowHandle(void* hwnd)
{
    g_host_window = static_cast<HWND>(hwnd);
}

void SetD3DDevice(void* device)
{
    g_d3d_device = static_cast<ID3D11Device*>(device);
}

bool LoadTextureFromImageFile(
    const std::filesystem::path& path,
    void** shader_resource_view,
    int* width,
    int* height,
    std::string* error)
{
    if (shader_resource_view == nullptr || width == nullptr || height == nullptr) {
        SetError(error, "Invalid texture output pointer.");
        return false;
    }
    *shader_resource_view = nullptr;
    *width = 0;
    *height = 0;

    if (g_d3d_device == nullptr) {
        SetError(error, "DirectX device is not ready.");
        return false;
    }
    if (path.empty() || !std::filesystem::exists(path)) {
        SetError(error, "Image file was not found.");
        return false;
    }

    const HRESULT co_result = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    const bool should_uninitialize_com = SUCCEEDED(co_result);
    if (FAILED(co_result) && co_result != RPC_E_CHANGED_MODE) {
        SetError(error, "Windows imaging could not initialize.");
        return false;
    }

    IWICImagingFactory* factory = nullptr;
    IWICBitmapDecoder* decoder = nullptr;
    IWICBitmapFrameDecode* frame = nullptr;
    IWICFormatConverter* converter = nullptr;
    ID3D11Texture2D* texture = nullptr;
    ID3D11ShaderResourceView* view = nullptr;

    auto cleanup = [&]() {
        ReleaseCom(view);
        ReleaseCom(texture);
        ReleaseCom(converter);
        ReleaseCom(frame);
        ReleaseCom(decoder);
        ReleaseCom(factory);
        if (should_uninitialize_com) {
            CoUninitialize();
        }
    };

    HRESULT hr = CoCreateInstance(
        CLSID_WICImagingFactory,
        nullptr,
        CLSCTX_INPROC_SERVER,
        IID_PPV_ARGS(&factory));
    if (FAILED(hr) || factory == nullptr) {
        cleanup();
        SetError(error, "Windows imaging factory is unavailable.");
        return false;
    }

    const std::wstring wide_path = path.wstring();
    hr = factory->CreateDecoderFromFilename(
        wide_path.c_str(),
        nullptr,
        GENERIC_READ,
        WICDecodeMetadataCacheOnLoad,
        &decoder);
    if (FAILED(hr) || decoder == nullptr) {
        cleanup();
        SetError(error, "Windows imaging could not decode this file.");
        return false;
    }

    hr = decoder->GetFrame(0, &frame);
    if (FAILED(hr) || frame == nullptr) {
        cleanup();
        SetError(error, "Image did not contain a readable frame.");
        return false;
    }

    UINT image_width = 0;
    UINT image_height = 0;
    hr = frame->GetSize(&image_width, &image_height);
    if (FAILED(hr) || image_width == 0 || image_height == 0) {
        cleanup();
        SetError(error, "Image size could not be read.");
        return false;
    }

    hr = factory->CreateFormatConverter(&converter);
    if (FAILED(hr) || converter == nullptr) {
        cleanup();
        SetError(error, "Image format conversion is unavailable.");
        return false;
    }

    hr = converter->Initialize(
        frame,
        GUID_WICPixelFormat32bppRGBA,
        WICBitmapDitherTypeNone,
        nullptr,
        0.0,
        WICBitmapPaletteTypeCustom);
    if (FAILED(hr)) {
        cleanup();
        SetError(error, "Image format is not supported by Windows imaging.");
        return false;
    }

    const UINT stride = image_width * 4;
    std::vector<unsigned char> pixels(static_cast<size_t>(stride) * static_cast<size_t>(image_height));
    hr = converter->CopyPixels(nullptr, stride, static_cast<UINT>(pixels.size()), pixels.data());
    if (FAILED(hr)) {
        cleanup();
        SetError(error, "Image pixels could not be read.");
        return false;
    }

    D3D11_TEXTURE2D_DESC texture_desc{};
    texture_desc.Width = image_width;
    texture_desc.Height = image_height;
    texture_desc.MipLevels = 1;
    texture_desc.ArraySize = 1;
    texture_desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    texture_desc.SampleDesc.Count = 1;
    texture_desc.Usage = D3D11_USAGE_DEFAULT;
    texture_desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;

    D3D11_SUBRESOURCE_DATA subresource{};
    subresource.pSysMem = pixels.data();
    subresource.SysMemPitch = stride;

    hr = g_d3d_device->CreateTexture2D(&texture_desc, &subresource, &texture);
    if (FAILED(hr) || texture == nullptr) {
        cleanup();
        SetError(error, "DirectX texture creation failed.");
        return false;
    }

    D3D11_SHADER_RESOURCE_VIEW_DESC view_desc{};
    view_desc.Format = texture_desc.Format;
    view_desc.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
    view_desc.Texture2D.MipLevels = 1;

    hr = g_d3d_device->CreateShaderResourceView(texture, &view_desc, &view);
    if (FAILED(hr) || view == nullptr) {
        cleanup();
        SetError(error, "DirectX preview view creation failed.");
        return false;
    }

    *shader_resource_view = view;
    *width = static_cast<int>(image_width);
    *height = static_cast<int>(image_height);
    view = nullptr;

    cleanup();
    return true;
}

void ReleaseTextureResource(void* shader_resource_view)
{
    ID3D11ShaderResourceView* view = static_cast<ID3D11ShaderResourceView*>(shader_resource_view);
    if (view != nullptr) {
        view->Release();
    }
}

bool PlayAudioPreviewFile(const std::filesystem::path& path, std::string* error)
{
    if (path.empty() || !std::filesystem::exists(path)) {
        SetError(error, "Audio file was not found.");
        return false;
    }

    StopAudioPreview();

    std::wstring command = L"open \"";
    command += path.wstring();
    command += L"\"";
    const std::wstring device_type = MciDeviceTypeForPath(path);
    if (!device_type.empty()) {
        command += L" type ";
        command += device_type;
    }
    command += L" alias ";
    command += kAudioPreviewAlias;

    MCIERROR result = SendMciCommand(command);
    if (result != 0) {
        SetError(error, MciErrorMessage(result));
        StopAudioPreview();
        return false;
    }

    command = L"play ";
    command += kAudioPreviewAlias;
    result = SendMciCommand(command);
    if (result != 0) {
        SetError(error, MciErrorMessage(result));
        StopAudioPreview();
        return false;
    }

    return true;
}

void StopAudioPreview()
{
    std::wstring command = L"stop ";
    command += kAudioPreviewAlias;
    SendMciCommand(command);
    command = L"close ";
    command += kAudioPreviewAlias;
    SendMciCommand(command);
}

bool IsAudioPreviewPlaying()
{
    std::array<wchar_t, 64> buffer{};
    std::wstring command = L"status ";
    command += kAudioPreviewAlias;
    command += L" mode";
    if (mciSendStringW(command.c_str(), buffer.data(), static_cast<UINT>(buffer.size()), nullptr) != 0) {
        return false;
    }
    return Lower(WideToUtf8(buffer.data())) == "playing";
}

void RequestWindowClose()
{
    PostQuitMessage(0);
}

void RequestWindowMinimize()
{
    HWND hwnd = g_host_window != nullptr ? g_host_window : GetActiveWindow();
    if (hwnd != nullptr) {
        ShowWindow(hwnd, SW_MINIMIZE);
    }
}

void RequestWindowMaximizeRestore()
{
    HWND hwnd = g_host_window != nullptr ? g_host_window : GetActiveWindow();
    if (hwnd == nullptr) {
        return;
    }
    ShowWindow(hwnd, IsZoomed(hwnd) ? SW_RESTORE : SW_MAXIMIZE);
}

bool IsHostWindowMaximized()
{
    HWND hwnd = g_host_window != nullptr ? g_host_window : GetActiveWindow();
    return hwnd != nullptr && IsZoomed(hwnd);
}

std::pair<float, float> HostWindowSize()
{
    HWND hwnd = g_host_window != nullptr ? g_host_window : GetActiveWindow();
    if (hwnd == nullptr) {
        return {0.0f, 0.0f};
    }

    RECT rect{};
    if (!GetWindowRect(hwnd, &rect)) {
        return {0.0f, 0.0f};
    }
    return {
        static_cast<float>(std::max(0L, rect.right - rect.left)),
        static_cast<float>(std::max(0L, rect.bottom - rect.top)),
    };
}

}
