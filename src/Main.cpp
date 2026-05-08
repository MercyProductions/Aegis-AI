#include "AegisChatApp.h"
#include "UiStyle.h"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <windowsx.h>
#include <d3d11.h>
#include <dwmapi.h>
#include <tchar.h>

#include "imgui.h"
#include "backends/imgui_impl_dx11.h"
#include "backends/imgui_impl_win32.h"

extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam);

namespace {

ID3D11Device* g_device = nullptr;
ID3D11DeviceContext* g_device_context = nullptr;
IDXGISwapChain* g_swap_chain = nullptr;
ID3D11RenderTargetView* g_main_render_target_view = nullptr;

#ifndef DWMWA_WINDOW_CORNER_PREFERENCE
#define DWMWA_WINDOW_CORNER_PREFERENCE 33
#endif
#ifndef DWMWCP_ROUND
#define DWMWCP_ROUND 2
#endif

bool CreateDeviceD3D(HWND hwnd)
{
    DXGI_SWAP_CHAIN_DESC sd{};
    sd.BufferCount = 2;
    sd.BufferDesc.Width = 0;
    sd.BufferDesc.Height = 0;
    sd.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    sd.BufferDesc.RefreshRate.Numerator = 60;
    sd.BufferDesc.RefreshRate.Denominator = 1;
    sd.Flags = DXGI_SWAP_CHAIN_FLAG_ALLOW_MODE_SWITCH;
    sd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sd.OutputWindow = hwnd;
    sd.SampleDesc.Count = 1;
    sd.SampleDesc.Quality = 0;
    sd.Windowed = TRUE;
    sd.SwapEffect = DXGI_SWAP_EFFECT_DISCARD;

    UINT create_device_flags = 0;
    D3D_FEATURE_LEVEL feature_level{};
    const D3D_FEATURE_LEVEL feature_level_array[2] = {
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_0,
    };

    const HRESULT result = D3D11CreateDeviceAndSwapChain(
        nullptr,
        D3D_DRIVER_TYPE_HARDWARE,
        nullptr,
        create_device_flags,
        feature_level_array,
        2,
        D3D11_SDK_VERSION,
        &sd,
        &g_swap_chain,
        &g_device,
        &feature_level,
        &g_device_context);

    return result == S_OK;
}

void CleanupRenderTarget()
{
    if (g_main_render_target_view) {
        g_main_render_target_view->Release();
        g_main_render_target_view = nullptr;
    }
}

void CreateRenderTarget()
{
    ID3D11Texture2D* back_buffer = nullptr;
    g_swap_chain->GetBuffer(0, IID_PPV_ARGS(&back_buffer));
    if (back_buffer) {
        g_device->CreateRenderTargetView(back_buffer, nullptr, &g_main_render_target_view);
        back_buffer->Release();
    }
}

void CleanupDeviceD3D()
{
    CleanupRenderTarget();
    if (g_swap_chain) {
        g_swap_chain->Release();
        g_swap_chain = nullptr;
    }
    if (g_device_context) {
        g_device_context->Release();
        g_device_context = nullptr;
    }
    if (g_device) {
        g_device->Release();
        g_device = nullptr;
    }
}

LRESULT HitTestFramelessWindow(HWND hwnd, LPARAM lparam)
{
    RECT rect{};
    if (!GetWindowRect(hwnd, &rect)) {
        return HTCLIENT;
    }

    const UINT dpi = GetDpiForWindow(hwnd);
    const int frame_x = GetSystemMetricsForDpi(SM_CXFRAME, dpi) + GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi);
    const int frame_y = GetSystemMetricsForDpi(SM_CYFRAME, dpi) + GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi);
    const int drag_height = MulDiv(46, dpi, 96);
    const int chrome_width = MulDiv(136, dpi, 96);

    const int x = GET_X_LPARAM(lparam);
    const int y = GET_Y_LPARAM(lparam);
    if (y >= rect.top && y < rect.top + drag_height && x >= rect.right - chrome_width) {
        return HTCLIENT;
    }

    const bool left = x >= rect.left && x < rect.left + frame_x;
    const bool right = x < rect.right && x >= rect.right - frame_x;
    const bool top = y >= rect.top && y < rect.top + frame_y;
    const bool bottom = y < rect.bottom && y >= rect.bottom - frame_y;

    if (top && left) {
        return HTTOPLEFT;
    }
    if (top && right) {
        return HTTOPRIGHT;
    }
    if (bottom && left) {
        return HTBOTTOMLEFT;
    }
    if (bottom && right) {
        return HTBOTTOMRIGHT;
    }
    if (left) {
        return HTLEFT;
    }
    if (right) {
        return HTRIGHT;
    }
    if (top) {
        return HTTOP;
    }
    if (bottom) {
        return HTBOTTOM;
    }

    if (y >= rect.top && y < rect.top + drag_height && x < rect.right - chrome_width) {
        return HTCAPTION;
    }

    return HTCLIENT;
}

LRESULT WINAPI WndProc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam)
{
    switch (msg) {
    case WM_NCHITTEST:
        return HitTestFramelessWindow(hwnd, lparam);
    case WM_GETMINMAXINFO:
        if (MINMAXINFO* info = reinterpret_cast<MINMAXINFO*>(lparam)) {
            info->ptMinTrackSize.x = 860;
            info->ptMinTrackSize.y = 620;
        }
        return 0;
    default:
        break;
    }

    if (ImGui_ImplWin32_WndProcHandler(hwnd, msg, wparam, lparam)) {
        return true;
    }

    switch (msg) {
    case WM_SIZE:
        if (wparam != SIZE_MINIMIZED && g_device != nullptr) {
            CleanupRenderTarget();
            g_swap_chain->ResizeBuffers(0, static_cast<UINT>(LOWORD(lparam)), static_cast<UINT>(HIWORD(lparam)), DXGI_FORMAT_UNKNOWN, 0);
            CreateRenderTarget();
        }
        return 0;
    case WM_SYSCOMMAND:
        if ((wparam & 0xfff0) == SC_KEYMENU) {
            return 0;
        }
        break;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        break;
    }
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

}

int APIENTRY wWinMain(HINSTANCE instance, HINSTANCE, LPWSTR, int)
{
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);

    WNDCLASSEXW wc = {
        sizeof(WNDCLASSEXW),
        CS_CLASSDC,
        WndProc,
        0L,
        0L,
        instance,
        nullptr,
        nullptr,
        nullptr,
        nullptr,
        L"AegisChatBotDesktopWindow",
        nullptr
    };
    RegisterClassExW(&wc);

    HWND hwnd = CreateWindowW(
        wc.lpszClassName,
        L"Aegis ChatBot Desktop",
        WS_POPUP | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX,
        100,
        100,
        1500,
        940,
        nullptr,
        nullptr,
        wc.hInstance,
        nullptr);
    aegis::SetHostWindowHandle(hwnd);

    if (!CreateDeviceD3D(hwnd)) {
        CleanupDeviceD3D();
        UnregisterClassW(wc.lpszClassName, wc.hInstance);
        return 1;
    }
    aegis::SetD3DDevice(g_device);
    CreateRenderTarget();

    BOOL dark = TRUE;
    DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, &dark, sizeof(dark));
    const int corner_preference = DWMWCP_ROUND;
    DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, &corner_preference, sizeof(corner_preference));

    ShowWindow(hwnd, SW_SHOWDEFAULT);
    UpdateWindow(hwnd);
    SetForegroundWindow(hwnd);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.IniFilename = nullptr;
    if (ImFont* font = io.Fonts->AddFontFromFileTTF("C:\\Windows\\Fonts\\segoeui.ttf", 16.0f)) {
        io.FontDefault = font;
    }

    aegis::ApplyUiStyle();

    ImGui_ImplWin32_Init(hwnd);
    ImGui_ImplDX11_Init(g_device, g_device_context);

    {
    aegis::AegisChatApp app;
    app.Initialize();

    bool done = false;
    while (!done) {
        MSG msg;
        while (PeekMessageW(&msg, nullptr, 0U, 0U, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
            if (msg.message == WM_QUIT) {
                done = true;
            }
        }
        if (done) {
            break;
        }

        app.Tick();

        ImGui_ImplDX11_NewFrame();
        ImGui_ImplWin32_NewFrame();
        ImGui::NewFrame();
        app.Render();
        ImGui::Render();

        const float clear_color[4] = {0.052f, 0.060f, 0.068f, 1.0f};
        if (g_main_render_target_view == nullptr) {
            CreateRenderTarget();
        }
        g_device_context->OMSetRenderTargets(1, &g_main_render_target_view, nullptr);
        g_device_context->ClearRenderTargetView(g_main_render_target_view, clear_color);
        ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
        g_swap_chain->Present(1, 0);
    }
    }

    ImGui_ImplDX11_Shutdown();
    ImGui_ImplWin32_Shutdown();
    ImGui::DestroyContext();

    aegis::SetD3DDevice(nullptr);
    CleanupDeviceD3D();
    DestroyWindow(hwnd);
    UnregisterClassW(wc.lpszClassName, wc.hInstance);
    return 0;
}
