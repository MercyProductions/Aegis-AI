#pragma once

#include <filesystem>
#include <functional>
#include <string>
#include <utility>
#include <vector>

namespace aegis {

struct HttpResponse {
    int status_code = 0;
    std::string body;
    std::string raw_headers;
    std::string error;
};

struct DesktopSettings {
    std::string api_base_url = "http://127.0.0.1:8787";
    std::string core_api_base_url = "http://127.0.0.1:8788";
    std::filesystem::path backend_root;
    std::string backend_start_script = "scripts\\start-backend.ps1";
    bool auto_start_backend = true;
    int max_files = 160;
};

std::filesystem::path ExecutableDirectory();
std::filesystem::path AppDataDirectory();
std::filesystem::path ProjectDirectoryFromExecutable();
std::filesystem::path LocateDefaultBackendRoot();

DesktopSettings LoadDesktopSettings();
bool SaveDesktopSettings(const DesktopSettings& settings, std::string& error);
bool BackendHealthProjectRootMatches(
    const DesktopSettings& settings,
    const std::string& project_root,
    std::string* detail = nullptr);

std::wstring Utf8ToWide(const std::string& value);
std::string WideToUtf8(const std::wstring& value);
std::string GetEnvUtf8(const wchar_t* name);

std::string Trim(const std::string& value);
std::string Lower(std::string value);
std::string NormalizeHttpBaseUrl(const std::string& value, const std::string& fallback);
std::string EscapeJson(const std::string& value);
std::string UrlEncode(const std::string& value);
std::string JoinUrl(const std::string& base, const std::string& path);
std::string FormatBytes(long long size);
std::string NowTimeLabel();
std::string FirstJsonErrorDetail(const std::string& body);

HttpResponse HttpGet(const std::string& url);
HttpResponse HttpPostJson(const std::string& url, const std::string& body);
HttpResponse HttpPostJsonStream(
    const std::string& url,
    const std::string& body,
    const std::function<void(const std::string&)>& on_chunk);
HttpResponse HttpPutJson(const std::string& url, const std::string& body);
HttpResponse HttpDelete(const std::string& url);

bool StartBackendProcess(const DesktopSettings& settings, std::string& error);
void OpenExternalPath(const std::filesystem::path& path);
void SetHostWindowHandle(void* hwnd);
void SetD3DDevice(void* device);
bool LoadTextureFromImageFile(
    const std::filesystem::path& path,
    void** shader_resource_view,
    int* width,
    int* height,
    std::string* error);
void ReleaseTextureResource(void* shader_resource_view);
bool PlayAudioPreviewFile(const std::filesystem::path& path, std::string* error);
void StopAudioPreview();
bool IsAudioPreviewPlaying();
void RequestWindowClose();
void RequestWindowMinimize();
void RequestWindowMaximizeRestore();
bool IsHostWindowMaximized();
std::pair<float, float> HostWindowSize();

}
