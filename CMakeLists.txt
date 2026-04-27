cmake_minimum_required(VERSION 3.24)

project(AegisChatBotDesktop VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(AegisChatBotDesktop WIN32
    src/AegisChatApp.cpp
    src/AegisClient.cpp
    src/Json.cpp
    src/Main.cpp
    src/Platform.cpp
    src/UiStyle.cpp
    imgui/imgui.cpp
    imgui/imgui_draw.cpp
    imgui/imgui_tables.cpp
    imgui/imgui_widgets.cpp
    imgui/backends/imgui_impl_dx11.cpp
    imgui/backends/imgui_impl_win32.cpp
)

target_include_directories(AegisChatBotDesktop PRIVATE
    src
    imgui
    imgui/backends
)

target_compile_definitions(AegisChatBotDesktop PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    UNICODE
    _UNICODE
)

if(MSVC)
    target_compile_options(AegisChatBotDesktop PRIVATE /W4 /permissive- /EHsc /utf-8)
endif()

target_link_libraries(AegisChatBotDesktop PRIVATE
    d3d11
    dxgi
    dwmapi
    winhttp
    shell32
    ole32
)

add_custom_command(TARGET AegisChatBotDesktop POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CMAKE_CURRENT_SOURCE_DIR}/AegisChatBot.config.ini"
        "$<TARGET_FILE_DIR:AegisChatBotDesktop>/AegisChatBot.config.ini"
)
