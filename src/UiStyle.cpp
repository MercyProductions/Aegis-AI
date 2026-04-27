#include "UiStyle.h"

#include "imgui.h"

namespace aegis {

void ApplyUiStyle()
{
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowPadding = ImVec2(14.0f, 12.0f);
    style.FramePadding = ImVec2(10.0f, 7.0f);
    style.ItemSpacing = ImVec2(10.0f, 8.0f);
    style.ItemInnerSpacing = ImVec2(8.0f, 6.0f);
    style.ScrollbarSize = 12.0f;
    style.WindowBorderSize = 0.0f;
    style.ChildBorderSize = 1.0f;
    style.PopupBorderSize = 1.0f;
    style.FrameBorderSize = 0.0f;
    style.WindowRounding = 0.0f;
    style.ChildRounding = 7.0f;
    style.FrameRounding = 5.0f;
    style.PopupRounding = 6.0f;
    style.ScrollbarRounding = 8.0f;
    style.GrabRounding = 4.0f;
    style.TabRounding = 5.0f;

    ImVec4* colors = style.Colors;
    colors[ImGuiCol_Text] = ImVec4(0.91f, 0.94f, 0.95f, 1.00f);
    colors[ImGuiCol_TextDisabled] = ImVec4(0.48f, 0.54f, 0.58f, 1.00f);
    colors[ImGuiCol_WindowBg] = ImVec4(0.052f, 0.060f, 0.068f, 1.00f);
    colors[ImGuiCol_ChildBg] = ImVec4(0.073f, 0.084f, 0.095f, 1.00f);
    colors[ImGuiCol_PopupBg] = ImVec4(0.075f, 0.086f, 0.100f, 1.00f);
    colors[ImGuiCol_Border] = ImVec4(0.18f, 0.21f, 0.23f, 1.00f);
    colors[ImGuiCol_BorderShadow] = ImVec4(0.00f, 0.00f, 0.00f, 0.00f);
    colors[ImGuiCol_FrameBg] = ImVec4(0.11f, 0.13f, 0.15f, 1.00f);
    colors[ImGuiCol_FrameBgHovered] = ImVec4(0.16f, 0.20f, 0.22f, 1.00f);
    colors[ImGuiCol_FrameBgActive] = ImVec4(0.16f, 0.38f, 0.37f, 1.00f);
    colors[ImGuiCol_TitleBg] = ImVec4(0.045f, 0.052f, 0.060f, 1.00f);
    colors[ImGuiCol_TitleBgActive] = ImVec4(0.060f, 0.070f, 0.080f, 1.00f);
    colors[ImGuiCol_MenuBarBg] = ImVec4(0.09f, 0.10f, 0.115f, 1.00f);
    colors[ImGuiCol_ScrollbarBg] = ImVec4(0.05f, 0.055f, 0.062f, 1.00f);
    colors[ImGuiCol_ScrollbarGrab] = ImVec4(0.25f, 0.29f, 0.32f, 1.00f);
    colors[ImGuiCol_ScrollbarGrabHovered] = ImVec4(0.30f, 0.36f, 0.38f, 1.00f);
    colors[ImGuiCol_CheckMark] = ImVec4(0.25f, 0.86f, 0.68f, 1.00f);
    colors[ImGuiCol_SliderGrab] = ImVec4(0.22f, 0.72f, 0.66f, 1.00f);
    colors[ImGuiCol_SliderGrabActive] = ImVec4(0.91f, 0.62f, 0.24f, 1.00f);
    colors[ImGuiCol_Button] = ImVec4(0.13f, 0.16f, 0.18f, 1.00f);
    colors[ImGuiCol_ButtonHovered] = ImVec4(0.18f, 0.24f, 0.25f, 1.00f);
    colors[ImGuiCol_ButtonActive] = ImVec4(0.22f, 0.67f, 0.61f, 1.00f);
    colors[ImGuiCol_Header] = ImVec4(0.13f, 0.18f, 0.19f, 1.00f);
    colors[ImGuiCol_HeaderHovered] = ImVec4(0.17f, 0.25f, 0.26f, 1.00f);
    colors[ImGuiCol_HeaderActive] = ImVec4(0.22f, 0.67f, 0.61f, 1.00f);
    colors[ImGuiCol_Separator] = ImVec4(0.20f, 0.23f, 0.26f, 1.00f);
    colors[ImGuiCol_ResizeGrip] = ImVec4(0.22f, 0.67f, 0.61f, 0.30f);
    colors[ImGuiCol_ResizeGripHovered] = ImVec4(0.22f, 0.67f, 0.61f, 0.70f);
    colors[ImGuiCol_Tab] = ImVec4(0.10f, 0.12f, 0.14f, 1.00f);
    colors[ImGuiCol_TabHovered] = ImVec4(0.18f, 0.24f, 0.25f, 1.00f);
    colors[ImGuiCol_TabActive] = ImVec4(0.17f, 0.29f, 0.29f, 1.00f);
    colors[ImGuiCol_TableHeaderBg] = ImVec4(0.10f, 0.12f, 0.14f, 1.00f);
    colors[ImGuiCol_TableBorderStrong] = ImVec4(0.20f, 0.23f, 0.26f, 1.00f);
    colors[ImGuiCol_TableBorderLight] = ImVec4(0.13f, 0.15f, 0.17f, 1.00f);
    colors[ImGuiCol_TextSelectedBg] = ImVec4(0.22f, 0.67f, 0.61f, 0.35f);
}

}
