from __future__ import annotations

import re
import textwrap
import uuid

from .project_scaffold_targets import title_from_name as scaffold_title_from_name


def cpp_cmake_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 17)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_executable(${{PROJECT_NAME}} src/main.cpp)
            target_include_directories(${{PROJECT_NAME}} PRIVATE include)

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_include_directories(${{PROJECT_NAME}}_smoke PRIVATE include)
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        f"include/{native_name}/version.h": _strip(
            f"""
            #pragma once

            namespace {native_name} {{
            inline constexpr const char* kAppName = "{title}";
            inline constexpr const char* kVersion = "0.1.0";
            }}
            """
        ),
        "src/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <string>

            #include "{native_name}/version.h"

            int main(int argc, char** argv)
            {{
                const char* name = argc > 1 ? argv[1] : "Aegis";
                std::cout << "Hello, world!\\n";
                std::cout << {native_name}::kAppName << " " << {native_name}::kVersion
                          << " ready for " << name << "\\n";
                if (argc <= 1 || std::string(argv[1]) != "--aegis-validate")
                {{
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                }}
                return 0;
            }}
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include <cassert>
            #include <string>

            #include "{native_name}/version.h"

            int main()
            {{
                assert(std::string({native_name}::kVersion) == "0.1.0");
                return 0;
            }}
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent
            APP_NAME = "{native_name}"
            BUILD_DIR = Path(
                os.environ.get(
                    "AEGIS_CMAKE_BUILD_DIR",
                    Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                )
            )


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True)
                return completed.returncode


            def find_app_executable() -> Path | None:
                names = {{APP_NAME, APP_NAME + ".exe"}}
                for candidate in BUILD_DIR.rglob("*"):
                    if candidate.is_file() and candidate.name in names:
                        return candidate
                return None


            def run_generated_app() -> int:
                app = find_app_executable()
                if app is None:
                    print("Generated executable was not found under build/.", file=sys.stderr)
                    return 2
                command = [str(app), "--aegis-validate"]
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Hello, world!" not in completed.stdout:
                    print("Generated app ran, but expected hello-world output was not found.", file=sys.stderr)
                    return 1
                return 0


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                if code != 0:
                    return code

                code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                if code != 0:
                    return code

                code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                if code != 0:
                    return code

                return run_generated_app()


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            .vs
            .vscode
            *.user
            *.obj
            *.pdb
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            C++ CMake CLI generated by Aegis Project Builder.

            ## Build

            ```bash
            cmake -S . -B build
            cmake --build build
            ```

            ## Validation

            ```bash
            python build.py
            ```
            """
        ),
    }


def cpp_cmake_dll_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    macro_base = re.sub(r"[^A-Za-z0-9_]+", "_", native_name).strip("_").upper() or "AEGIS_LIBRARY"
    export_macro = f"{macro_base}_API"
    build_macro = f"{macro_base}_EXPORTS"
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 17)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_library(${{PROJECT_NAME}} SHARED
              src/library.cpp
            )
            target_include_directories(${{PROJECT_NAME}}
              PUBLIC
                $<BUILD_INTERFACE:${{CMAKE_CURRENT_SOURCE_DIR}}/include>
                $<INSTALL_INTERFACE:include>
            )
            target_compile_definitions(${{PROJECT_NAME}} PRIVATE {build_macro})
            target_compile_features(${{PROJECT_NAME}} PUBLIC cxx_std_17)

            add_executable(${{PROJECT_NAME}}_host host/main.cpp)
            target_include_directories(${{PROJECT_NAME}}_host PRIVATE include)
            target_compile_features(${{PROJECT_NAME}}_host PRIVATE cxx_std_17)
            target_link_libraries(${{PROJECT_NAME}}_host PRIVATE ${{CMAKE_DL_LIBS}})

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}})
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        "CMakePresets.json": _strip(
            """
            {
              "version": 6,
              "configurePresets": [
                {
                  "name": "default",
                  "displayName": "Default build",
                  "generator": "Ninja",
                  "binaryDir": "${sourceDir}/build",
                  "cacheVariables": {
                    "CMAKE_BUILD_TYPE": "Release",
                    "BUILD_TESTING": "ON"
                  }
                }
              ],
              "buildPresets": [
                {
                  "name": "default",
                  "configurePreset": "default"
                }
              ],
              "testPresets": [
                {
                  "name": "default",
                  "configurePreset": "default",
                  "output": {
                    "outputOnFailure": true
                  }
                }
              ]
            }
            """
        ),
        f"include/{native_name}/library.h": _strip(
            f"""
            #pragma once

            #if defined(_WIN32)
              #if defined({build_macro})
                #define {export_macro} __declspec(dllexport)
              #else
                #define {export_macro} __declspec(dllimport)
              #endif
            #else
              #define {export_macro} __attribute__((visibility("default")))
            #endif

            extern "C" {export_macro} int aegis_add(int left, int right);
            extern "C" {export_macro} const char* aegis_library_name();
            extern "C" {export_macro} const char* aegis_plugin_version();
            extern "C" {export_macro} const char* aegis_plugin_description();
            """
        ),
        "src/library.cpp": _strip(
            f"""
            #include "{native_name}/library.h"

            int aegis_add(int left, int right)
            {{
                return left + right;
            }}

            const char* aegis_library_name()
            {{
                return "{title}";
            }}

            const char* aegis_plugin_version()
            {{
                return "0.1.0";
            }}

            const char* aegis_plugin_description()
            {{
                return "Aegis generated native DLL/shared-library plugin with a stable exported C ABI.";
            }}
            """
        ),
        "host/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <stdexcept>
            #include <string>

            #if defined(_WIN32)
            #define WIN32_LEAN_AND_MEAN
            #include <windows.h>
            #else
            #include <dlfcn.h>
            #endif

            namespace {{

            class SharedLibrary {{
            public:
                explicit SharedLibrary(const std::string& path)
                {{
            #if defined(_WIN32)
                    handle_ = LoadLibraryA(path.c_str());
            #else
                    handle_ = dlopen(path.c_str(), RTLD_NOW);
            #endif
                    if (handle_ == nullptr)
                    {{
                        throw std::runtime_error("Unable to load plugin library: " + path);
                    }}
                }}

                ~SharedLibrary()
                {{
            #if defined(_WIN32)
                    if (handle_ != nullptr)
                    {{
                        FreeLibrary(static_cast<HMODULE>(handle_));
                    }}
            #else
                    if (handle_ != nullptr)
                    {{
                        dlclose(handle_);
                    }}
            #endif
                }}

                SharedLibrary(const SharedLibrary&) = delete;
                SharedLibrary& operator=(const SharedLibrary&) = delete;

                template <typename Fn>
                Fn symbol(const char* name) const
                {{
            #if defined(_WIN32)
                    FARPROC value = GetProcAddress(static_cast<HMODULE>(handle_), name);
            #else
                    void* value = dlsym(handle_, name);
            #endif
                    if (value == nullptr)
                    {{
                        throw std::runtime_error(std::string("Missing exported symbol: ") + name);
                    }}
                    return reinterpret_cast<Fn>(value);
                }}

            private:
                void* handle_{{nullptr}};
            }};

            }} // namespace

            int main(int argc, char** argv)
            {{
                const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";
                const int library_arg = validate ? 2 : 1;
                if (argc <= library_arg)
                {{
                    std::cerr << "Usage: {native_name}_host [--aegis-validate] <path-to-plugin-library>\\n";
                    return 2;
                }}

                try
                {{
                    SharedLibrary library(argv[library_arg]);
                    using AddFn = int (*)(int, int);
                    using StringFn = const char* (*)();

                    const auto add = library.symbol<AddFn>("aegis_add");
                    const auto name = library.symbol<StringFn>("aegis_library_name");
                    const auto version = library.symbol<StringFn>("aegis_plugin_version");
                    const auto description = library.symbol<StringFn>("aegis_plugin_description");

                    const int result = add(21, 21);
                    std::cout << "Host loaded plugin: " << name() << "\\n";
                    std::cout << "Plugin version: " << version() << "\\n";
                    std::cout << "Plugin description: " << description() << "\\n";
                    std::cout << "aegis_add(21, 21)=" << result << "\\n";

                    if (result != 42 || std::string(name()).empty() || std::string(version()).empty())
                    {{
                        std::cerr << "Plugin validation failed.\\n";
                        return 3;
                    }}

                    if (!validate)
                    {{
                        std::cout << "Press Enter to close...";
                        std::string line;
                        std::getline(std::cin, line);
                    }}
                    return 0;
                }}
                catch (const std::exception& error)
                {{
                    std::cerr << error.what() << "\\n";
                    return 1;
                }}
            }}
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include <cstring>

            #include "{native_name}/library.h"

            int main()
            {{
                if (aegis_add(2, 3) != 5) {{
                    return 1;
                }}
                if (std::strlen(aegis_library_name()) == 0) {{
                    return 2;
                }}
                if (std::strlen(aegis_plugin_version()) == 0) {{
                    return 3;
                }}
                return std::strlen(aegis_plugin_description()) > 0 ? 0 : 4;
            }}
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent
            APP_NAME = "{native_name}"
            BUILD_DIR = Path(
                os.environ.get(
                    "AEGIS_CMAKE_BUILD_DIR",
                    Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                )
            )


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def find_built_file(names: set[str]) -> Path | None:
                for candidate in BUILD_DIR.rglob("*"):
                    if candidate.is_file() and candidate.name in names:
                        return candidate
                return None


            def find_plugin_library() -> Path | None:
                return find_built_file({{
                    APP_NAME + ".dll",
                    "lib" + APP_NAME + ".so",
                    "lib" + APP_NAME + ".dylib",
                }})


            def find_host_executable() -> Path | None:
                return find_built_file({{
                    APP_NAME + "_host",
                    APP_NAME + "_host.exe",
                }})


            def run_host_validation() -> int:
                host = find_host_executable()
                library = find_plugin_library()
                if host is None:
                    print("Generated host executable was not found under build/.", file=sys.stderr)
                    return 3
                if library is None:
                    print("Generated plugin library was not found under build/.", file=sys.stderr)
                    return 4
                completed = subprocess.run(
                    [str(host), "--aegis-validate", str(library)],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                )
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Host loaded plugin:" not in completed.stdout or "aegis_add(21, 21)=42" not in completed.stdout:
                    print("Expected host/plugin validation output was not found.", file=sys.stderr)
                    return 5
                return 0


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                configure = ["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator]
                code = run(configure)
                if code != 0:
                    return code

                code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                if code != 0:
                    return code

                code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                if code != 0:
                    return code

                return run_host_validation()


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            *.dll
            *.lib
            *.exp
            *.so
            *.dylib
            *.out
            *.obj
            *.pdb
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            C++17 DLL/shared-library project generated by Aegis Project Builder.

            ## What It Includes

            - `include/{native_name}/library.h` with portable export macros.
            - `src/library.cpp` with exported example functions.
            - `host/main.cpp` with a runtime loader that verifies exported symbols.
            - `tests/smoke.cpp` linked against the library.
            - `build.py` that configures, builds, runs CTest, and launches the host validation path.

            ## Build And Validate

            ```powershell
            python build.py
            ```

            The generated library exports:

            - `aegis_add(int left, int right)`
            - `aegis_library_name()`
            - `aegis_plugin_version()`
            - `aegis_plugin_description()`
            """
        ),
    }


def cpp_imgui_win32_dx11_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 20)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_library(${{PROJECT_NAME}}_core
              src/app_state.cpp
            )
            target_include_directories(${{PROJECT_NAME}}_core PUBLIC include vendor/imgui_shim)
            target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_20)

            add_executable(${{PROJECT_NAME}} src/main.cpp)
            target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        f"include/{native_name}/app_state.h": _strip(
            f"""
            #pragma once

            #include <cstdint>
            #include <string>
            #include <vector>

            namespace {native_name} {{

            struct FrameMetrics {{
                float delta_seconds{{1.0f / 60.0f}};
                float frame_time_ms{{16.67f}};
                int draw_calls{{0}};
                int visible_entities{{0}};
            }};

            struct ToolLogEntry {{
                std::string level;
                std::string message;
            }};

            class AppState {{
            public:
                AppState();

                void add_log(std::string level, std::string message);
                void tick(float delta_seconds);

                [[nodiscard]] const FrameMetrics& metrics() const noexcept;
                [[nodiscard]] const std::vector<ToolLogEntry>& log() const noexcept;
                [[nodiscard]] std::string summary() const;

            private:
                FrameMetrics metrics_;
                std::vector<ToolLogEntry> log_;
            }};

            void render_editor_panels(AppState& state);

            }} // namespace {native_name}
            """
        ),
        "src/app_state.cpp": _strip(
            f"""
            #include "{native_name}/app_state.h"

            #include <algorithm>
            #include <cstddef>
            #include <sstream>
            #include <utility>

            #include "imgui.h"

            namespace {native_name} {{

            AppState::AppState()
            {{
                add_log("info", "Aegis ImGui tooling scaffold initialized.");
                add_log("info", "Use this project for editors, overlays, debug panels, and game tooling.");
            }}

            void AppState::add_log(std::string level, std::string message)
            {{
                log_.push_back(ToolLogEntry{{std::move(level), std::move(message)}});
                if (log_.size() > 200)
                {{
                    log_.erase(log_.begin(), log_.begin() + static_cast<std::ptrdiff_t>(log_.size() - 200));
                }}
            }}

            void AppState::tick(float delta_seconds)
            {{
                metrics_.delta_seconds = delta_seconds;
                metrics_.frame_time_ms = delta_seconds * 1000.0f;
                metrics_.draw_calls += 3;
                metrics_.visible_entities = std::max(1, metrics_.visible_entities + 1);
            }}

            const FrameMetrics& AppState::metrics() const noexcept
            {{
                return metrics_;
            }}

            const std::vector<ToolLogEntry>& AppState::log() const noexcept
            {{
                return log_;
            }}

            std::string AppState::summary() const
            {{
                std::ostringstream stream;
                stream << "Inspector panels ready: viewport, assets, frame metrics, logs";
                stream << " | logs=" << log_.size();
                stream << " | visible_entities=" << metrics_.visible_entities;
                return stream.str();
            }}

            void render_editor_panels(AppState& state)
            {{
                const FrameMetrics& frame = state.metrics();

                if (ImGui::Begin("Aegis Game Tool"))
                {{
                    ImGui::TextUnformatted("Viewport, entity inspector, and asset workflow shell");
                    ImGui::Separator();
                    ImGui::Text("Delta: %.4f", frame.delta_seconds);
                    ImGui::Text("Frame time: %.2f ms", frame.frame_time_ms);
                    ImGui::Text("Draw calls: %d", frame.draw_calls);
                    ImGui::Text("Visible entities: %d", frame.visible_entities);
                }}
                ImGui::End();

                if (ImGui::Begin("Asset Browser"))
                {{
                    ImGui::TextUnformatted("Drop parsers, importers, and package viewers here.");
                }}
                ImGui::End();

                if (ImGui::Begin("Tool Log"))
                {{
                    for (const ToolLogEntry& entry : state.log())
                    {{
                        ImGui::Text("[%s] %s", entry.level.c_str(), entry.message.c_str());
                    }}
                }}
                ImGui::End();
            }}

            }} // namespace {native_name}
            """
        ),
        "src/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <string>

            #include "imgui.h"
            #include "{native_name}/app_state.h"

            int main(int argc, char** argv)
            {{
                const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                ImGui::CreateContext();
                {native_name}::AppState state;
                state.tick(1.0f / 60.0f);
                {native_name}::render_editor_panels(state);
                ImGui::Render();

                const std::string summary = state.summary();
                std::cout << "{title} Dear ImGui tooling starter\\n";
                std::cout << summary << "\\n";

                if (summary.find("Inspector panels ready") == std::string::npos)
                {{
                    std::cerr << "ImGui tool shell did not render expected panels.\\n";
                    ImGui::DestroyContext();
                    return 2;
                }}

                if (!validate)
                {{
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                }}

                ImGui::DestroyContext();
                return 0;
            }}
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include <string>

            #include "{native_name}/app_state.h"

            int main()
            {{
                {native_name}::AppState state;
                state.tick(1.0f / 120.0f);
                state.add_log("test", "smoke validation");

                const std::string summary = state.summary();
                if (summary.find("Inspector panels ready") == std::string::npos)
                {{
                    return 1;
                }}
                return state.log().empty() ? 2 : 0;
            }}
            """
        ),
        "vendor/imgui_shim/imgui.h": _strip(
            """
            #pragma once

            #include <cstdarg>

            namespace ImGui {

            inline void CreateContext() {}
            inline void DestroyContext() {}
            inline void Render() {}
            inline bool Begin(const char*) { return true; }
            inline void End() {}
            inline void Separator() {}
            inline void TextUnformatted(const char*) {}
            inline void Text(const char*, ...) {}

            } // namespace ImGui
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent
            APP_NAME = "{native_name}"
            BUILD_DIR = Path(
                os.environ.get(
                    "AEGIS_CMAKE_BUILD_DIR",
                    Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                )
            )


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def find_app_executable() -> Path | None:
                names = {{APP_NAME, APP_NAME + ".exe"}}
                build_root = ROOT / "build"
                for candidate in build_root.rglob("*"):
                    if candidate.is_file() and candidate.name in names:
                        return candidate
                return None


            def run_generated_app() -> int:
                app = find_app_executable()
                if app is None:
                    print("Generated ImGui tool executable was not found under build/.", file=sys.stderr)
                    return 3
                completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Dear ImGui tooling starter" not in completed.stdout:
                    print("Expected ImGui tooling validation output was not found.", file=sys.stderr)
                    return 4
                return 0


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake 3.20+ is required to validate this ImGui scaffold.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                code = run(["cmake", "-S", ".", "-B", "build", "-DBUILD_TESTING=ON", *generator])
                if code != 0:
                    return code

                code = run(["cmake", "--build", "build", "--config", "Release"])
                if code != 0:
                    return code

                code = run(["ctest", "--test-dir", "build", "-C", "Release", "--output-on-failure"])
                if code != 0:
                    return code

                return run_generated_app()


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            .vs
            .vscode
            *.user
            *.obj
            *.pdb
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            C++20 Dear ImGui-style game tooling scaffold generated by Aegis Project Builder.

            ## What This Gives You

            - A validated CMake project for ImGui-style editor panels and game tooling.
            - `AppState` for frame metrics, entity/asset workflow state, and tool logs.
            - A dependency-free ImGui validation shim so the project can build immediately.
            - A clear place to swap in real Dear ImGui Win32/DX11 backends when you are ready.

            ## Validate

            ```powershell
            python build.py
            ```

            ## Upgrading To Real Dear ImGui

            Replace `vendor/imgui_shim/imgui.h` with the official Dear ImGui source tree and update
            `CMakeLists.txt` to compile `imgui.cpp`, `imgui_draw.cpp`, `imgui_tables.cpp`,
            `imgui_widgets.cpp`, and the Win32/DX11 backend files from `backends/`.
            """
        ),
    }


def cpp_game_loop_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 20)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_library(${{PROJECT_NAME}}_engine src/engine.cpp)
            target_include_directories(${{PROJECT_NAME}}_engine PUBLIC include)
            target_compile_features(${{PROJECT_NAME}}_engine PUBLIC cxx_std_20)

            add_executable(${{PROJECT_NAME}} src/main.cpp)
            target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_engine)

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_engine)
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        f"include/{native_name}/engine.h": _strip(
            f"""
            #pragma once

            #include <cstddef>
            #include <cstdint>
            #include <string>
            #include <unordered_map>
            #include <vector>

            namespace {native_name} {{

            struct AssetRecord {{
                std::string id;
                std::string path;
                std::string type;
            }};

            struct SimulationStats {{
                std::uint64_t tick{{0}};
                double elapsed_seconds{{0.0}};
                std::size_t loaded_assets{{0}};
            }};

            class AssetRegistry {{
            public:
                bool add(AssetRecord record);
                [[nodiscard]] const AssetRecord* find(const std::string& id) const;
                [[nodiscard]] std::size_t size() const noexcept;

            private:
                std::unordered_map<std::string, AssetRecord> assets_;
            }};

            class FixedStepSimulation {{
            public:
                explicit FixedStepSimulation(double step_seconds = 1.0 / 60.0);

                void load_default_assets();
                void tick();
                void run_for_ticks(std::uint64_t count);

                [[nodiscard]] const SimulationStats& stats() const noexcept;
                [[nodiscard]] const AssetRegistry& assets() const noexcept;
                [[nodiscard]] std::string validation_report() const;

            private:
                double step_seconds_;
                SimulationStats stats_;
                AssetRegistry assets_;
            }};

            }} // namespace {native_name}
            """
        ),
        "src/engine.cpp": _strip(
            f"""
            #include "{native_name}/engine.h"

            #include <sstream>
            #include <utility>

            namespace {native_name} {{

            bool AssetRegistry::add(AssetRecord record)
            {{
                if (record.id.empty() || record.path.empty())
                {{
                    return false;
                }}
                const std::string id = record.id;
                return assets_.emplace(id, std::move(record)).second;
            }}

            const AssetRecord* AssetRegistry::find(const std::string& id) const
            {{
                const auto found = assets_.find(id);
                return found == assets_.end() ? nullptr : &found->second;
            }}

            std::size_t AssetRegistry::size() const noexcept
            {{
                return assets_.size();
            }}

            FixedStepSimulation::FixedStepSimulation(double step_seconds)
                : step_seconds_(step_seconds)
            {{
            }}

            void FixedStepSimulation::load_default_assets()
            {{
                assets_.add(AssetRecord{{"player", "assets/player.placeholder", "entity"}});
                assets_.add(AssetRecord{{"level_01", "assets/level_01.placeholder", "level"}});
                assets_.add(AssetRecord{{"debug_font", "assets/debug_font.placeholder", "font"}});
                stats_.loaded_assets = assets_.size();
            }}

            void FixedStepSimulation::tick()
            {{
                ++stats_.tick;
                stats_.elapsed_seconds += step_seconds_;
                stats_.loaded_assets = assets_.size();
            }}

            void FixedStepSimulation::run_for_ticks(std::uint64_t count)
            {{
                for (std::uint64_t index = 0; index < count; ++index)
                {{
                    tick();
                }}
            }}

            const SimulationStats& FixedStepSimulation::stats() const noexcept
            {{
                return stats_;
            }}

            const AssetRegistry& FixedStepSimulation::assets() const noexcept
            {{
                return assets_;
            }}

            std::string FixedStepSimulation::validation_report() const
            {{
                std::ostringstream stream;
                stream << "Game loop validation passed"
                       << " | ticks=" << stats_.tick
                       << " | elapsed=" << stats_.elapsed_seconds
                       << " | assets=" << stats_.loaded_assets;
                return stream.str();
            }}

            }} // namespace {native_name}
            """
        ),
        "src/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <string>

            #include "{native_name}/engine.h"

            int main(int argc, char** argv)
            {{
                const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                {native_name}::FixedStepSimulation simulation;
                simulation.load_default_assets();
                simulation.run_for_ticks(validate ? 5 : 120);

                std::cout << "{title} game sandbox\\n";
                std::cout << simulation.validation_report() << "\\n";

                if (simulation.stats().tick == 0 || simulation.assets().find("player") == nullptr)
                {{
                    std::cerr << "Simulation did not load required starter state.\\n";
                    return 2;
                }}

                if (!validate)
                {{
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                }}
                return 0;
            }}
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include "{native_name}/engine.h"

            #include <string>

            int main()
            {{
                {native_name}::FixedStepSimulation simulation;
                simulation.load_default_assets();
                simulation.run_for_ticks(8);

                if (simulation.stats().tick != 8)
                {{
                    return 1;
                }}
                if (simulation.assets().find("level_01") == nullptr)
                {{
                    return 2;
                }}
                return simulation.validation_report().find("Game loop validation passed") == std::string::npos ? 3 : 0;
            }}
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent
            APP_NAME = "{native_name}"
            BUILD_DIR = Path(
                os.environ.get(
                    "AEGIS_CMAKE_BUILD_DIR",
                    Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                )
            )


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def find_app_executable() -> Path | None:
                names = {{APP_NAME, APP_NAME + ".exe"}}
                for candidate in BUILD_DIR.rglob("*"):
                    if candidate.is_file() and candidate.name in names:
                        return candidate
                return None


            def run_generated_app() -> int:
                app = find_app_executable()
                if app is None:
                    print("Generated game sandbox executable was not found under build/.", file=sys.stderr)
                    return 3
                completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Game loop validation passed" not in completed.stdout:
                    print("Expected game-loop validation output was not found.", file=sys.stderr)
                    return 4
                return 0


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake 3.20+ is required to validate this game sandbox.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                if code != 0:
                    return code

                code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                if code != 0:
                    return code

                code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                if code != 0:
                    return code

                return run_generated_app()


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            .vs
            .vscode
            *.user
            *.obj
            *.pdb
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            C++20 game-loop sandbox generated by Aegis Project Builder.

            ## Included Systems

            - Fixed-step simulation loop.
            - Asset registry for game/editor tooling.
            - CLI validation mode for automated build repair loops.
            - Smoke test that validates ticks, assets, and reporting.

            ## Validate

            ```powershell
            python build.py
            ```
            """
        ),
    }

def cpp_msvc_console_template(project_name: str) -> dict[str, str]:
    title = _title_from_name(project_name)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name).strip(".-") or "aegis-console"
    root_namespace = re.sub(r"[^A-Za-z0-9_]+", "_", safe_name).strip("_") or "AegisConsole"
    if root_namespace[0].isdigit():
        root_namespace = f"App_{root_namespace}"
    project_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.cpp.msvc.{safe_name}")).upper() + "}"
    source_filter_guid = "{" + str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis.cpp.msvc.{safe_name}.source")).upper() + "}"
    return {
        f"{safe_name}.sln": _strip(
            f"""
            Microsoft Visual Studio Solution File, Format Version 12.00
            # Visual Studio Version 17
            VisualStudioVersion = 17.0.31903.59
            MinimumVisualStudioVersion = 10.0.40219.1
            Project("{{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}}") = "{safe_name}", "{safe_name}.vcxproj", "{project_guid}"
            EndProject
            Global
                GlobalSection(SolutionConfigurationPlatforms) = preSolution
                    Debug|x64 = Debug|x64
                    Release|x64 = Release|x64
                EndGlobalSection
                GlobalSection(ProjectConfigurationPlatforms) = postSolution
                    {project_guid}.Debug|x64.ActiveCfg = Debug|x64
                    {project_guid}.Debug|x64.Build.0 = Debug|x64
                    {project_guid}.Release|x64.ActiveCfg = Release|x64
                    {project_guid}.Release|x64.Build.0 = Release|x64
                EndGlobalSection
                GlobalSection(SolutionProperties) = preSolution
                    HideSolutionNode = FALSE
                EndGlobalSection
            EndGlobal
            """
        ),
        f"{safe_name}.vcxproj": _strip(
            f"""
            <?xml version="1.0" encoding="utf-8"?>
            <Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemGroup Label="ProjectConfigurations">
                <ProjectConfiguration Include="Debug|x64">
                  <Configuration>Debug</Configuration>
                  <Platform>x64</Platform>
                </ProjectConfiguration>
                <ProjectConfiguration Include="Release|x64">
                  <Configuration>Release</Configuration>
                  <Platform>x64</Platform>
                </ProjectConfiguration>
              </ItemGroup>
              <PropertyGroup Label="Globals">
                <VCProjectVersion>17.0</VCProjectVersion>
                <Keyword>Win32Proj</Keyword>
                <ProjectGuid>{project_guid}</ProjectGuid>
                <RootNamespace>{root_namespace}</RootNamespace>
                <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
              </PropertyGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
              <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
                <ConfigurationType>Application</ConfigurationType>
                <UseDebugLibraries>true</UseDebugLibraries>
                <PlatformToolset>v143</PlatformToolset>
                <CharacterSet>Unicode</CharacterSet>
              </PropertyGroup>
              <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
                <ConfigurationType>Application</ConfigurationType>
                <UseDebugLibraries>false</UseDebugLibraries>
                <PlatformToolset>v143</PlatformToolset>
                <WholeProgramOptimization>true</WholeProgramOptimization>
                <CharacterSet>Unicode</CharacterSet>
              </PropertyGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
              <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
                <ClCompile>
                  <WarningLevel>Level4</WarningLevel>
                  <SDLCheck>true</SDLCheck>
                  <ConformanceMode>true</ConformanceMode>
                  <LanguageStandard>stdcpp17</LanguageStandard>
                </ClCompile>
                <Link>
                  <SubSystem>Console</SubSystem>
                </Link>
              </ItemDefinitionGroup>
              <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
                <ClCompile>
                  <WarningLevel>Level4</WarningLevel>
                  <FunctionLevelLinking>true</FunctionLevelLinking>
                  <IntrinsicFunctions>true</IntrinsicFunctions>
                  <SDLCheck>true</SDLCheck>
                  <ConformanceMode>true</ConformanceMode>
                  <LanguageStandard>stdcpp17</LanguageStandard>
                </ClCompile>
                <Link>
                  <SubSystem>Console</SubSystem>
                  <EnableCOMDATFolding>true</EnableCOMDATFolding>
                  <OptimizeReferences>true</OptimizeReferences>
                </Link>
              </ItemDefinitionGroup>
              <ItemGroup>
                <ClCompile Include="src\\main.cpp" />
              </ItemGroup>
              <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
            </Project>
            """
        ),
        f"{safe_name}.vcxproj.filters": _strip(
            f"""
            <?xml version="1.0" encoding="utf-8"?>
            <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemGroup>
                <Filter Include="Source Files">
                  <UniqueIdentifier>{source_filter_guid}</UniqueIdentifier>
                  <Extensions>cpp;c;cc;cxx</Extensions>
                </Filter>
              </ItemGroup>
              <ItemGroup>
                <ClCompile Include="src\\main.cpp">
                  <Filter>Source Files</Filter>
                </ClCompile>
              </ItemGroup>
            </Project>
            """
        ),
        "src/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <string>

            int main()
            {{
                std::cout << "Hello, world!" << std::endl;
                std::cout << "{title} is running." << std::endl;
                std::cout << "Press Enter to close...";

                std::string line;
                std::getline(std::cin, line);
                return 0;
            }}
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            SOLUTION = Path(__file__).resolve().with_name("{safe_name}.sln")


            def candidate_msbuild_paths() -> list[Path]:
                candidates: list[Path] = []
                explicit = os.environ.get("MSBUILD_EXE")
                if explicit:
                    candidates.append(Path(explicit))

                program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")
                program_files = os.environ.get("ProgramFiles", r"C:\\Program Files")
                vswhere = Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
                if vswhere.exists():
                    try:
                        completed = subprocess.run(
                            [
                                str(vswhere),
                                "-latest",
                                "-products",
                                "*",
                                "-requires",
                                "Microsoft.Component.MSBuild",
                                "-find",
                                r"MSBuild\\**\\Bin\\MSBuild.exe",
                            ],
                            text=True,
                            capture_output=True,
                            check=False,
                        )
                        for line in completed.stdout.splitlines():
                            if line.strip():
                                candidates.append(Path(line.strip()))
                    except OSError:
                        pass

                for root in (Path(program_files), Path(program_files_x86)):
                    vs2022 = root / "Microsoft Visual Studio" / "2022"
                    for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                        candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "MSBuild.exe")
                        candidates.append(vs2022 / edition / "MSBuild" / "Current" / "Bin" / "amd64" / "MSBuild.exe")

                on_path = shutil.which("msbuild")
                if on_path:
                    candidates.append(Path(on_path))
                return candidates


            def find_msbuild() -> Path | None:
                seen: set[str] = set()
                for candidate in candidate_msbuild_paths():
                    key = str(candidate).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    if candidate.exists():
                        return candidate
                return None


            def main() -> int:
                if not SOLUTION.exists():
                    print(f"Solution not found: {{SOLUTION}}", file=sys.stderr)
                    return 2
                msbuild = find_msbuild()
                if msbuild is None:
                    print(
                        "MSBuild was not found. Install Visual Studio 2022 Build Tools "
                        "or set the MSBUILD_EXE environment variable.",
                        file=sys.stderr,
                    )
                    return 2

                command = [
                    str(msbuild),
                    str(SOLUTION),
                    "/p:Configuration=Release",
                    "/p:Platform=x64",
                ]
                print("Running:", " ".join(command))
                build_code = subprocess.call(command, cwd=str(SOLUTION.parent))
                if build_code != 0:
                    return build_code

                expected = SOLUTION.parent / "x64" / "Release" / "{safe_name}.exe"
                candidates = [expected] if expected.exists() else []
                candidates.extend(SOLUTION.parent.rglob("{safe_name}.exe"))
                exe = next((candidate for candidate in candidates if candidate.is_file()), None)
                if exe is None:
                    print("Compiled console executable was not found after MSBuild.", file=sys.stderr)
                    return 2

                run_command = [str(exe)]
                print("Running:", " ".join(run_command))
                completed = subprocess.run(run_command, cwd=str(SOLUTION.parent), input="\\n", text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Hello, world!" not in completed.stdout:
                    print("Generated console app ran, but expected hello-world output was not found.", file=sys.stderr)
                    return 1
                return 0


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            .vs
            x64
            Debug
            Release
            *.user
            *.obj
            *.pdb
            *.ilk
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Visual Studio C++ console solution generated by Aegis Project Builder.

            ## Build

            ```powershell
            python build.py
            ```

            ## Run

            `python build.py` builds the solution and runs the compiled console executable from `x64/Release`.
            The app prints `Hello, world!` and waits for Enter before closing.
            """
        ),
    }


def cpp_windows_service_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    service_symbol = re.sub(r"[^A-Za-z0-9]+", " ", title).title().replace(" ", "") or "AegisService"
    display_name = title if "service" in title.lower() else f"{title} Service"
    cpp_title = title.replace("\\", "\\\\").replace('"', '\\"')
    service_name_wide = service_symbol.replace("\\", "\\\\").replace('"', '\\"')
    display_name_wide = display_name.replace("\\", "\\\\").replace('"', '\\"')
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 17)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_library(${{PROJECT_NAME}}_core
              src/service_core.cpp
            )
            target_include_directories(${{PROJECT_NAME}}_core PUBLIC include)
            target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_17)

            add_executable(${{PROJECT_NAME}}
              src/service_main.cpp
            )
            target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

            if(WIN32)
              target_compile_definitions(${{PROJECT_NAME}} PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
              target_link_libraries(${{PROJECT_NAME}} PRIVATE advapi32)
            endif()

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        "CMakePresets.json": _strip(
            """
            {
              "version": 6,
              "configurePresets": [
                {
                  "name": "default",
                  "displayName": "Default build",
                  "generator": "Ninja",
                  "binaryDir": "${sourceDir}/build",
                  "cacheVariables": {
                    "CMAKE_BUILD_TYPE": "Release",
                    "BUILD_TESTING": "ON"
                  }
                }
              ],
              "buildPresets": [
                {
                  "name": "default",
                  "configurePreset": "default"
                }
              ],
              "testPresets": [
                {
                  "name": "default",
                  "configurePreset": "default",
                  "output": {
                    "outputOnFailure": true
                  }
                }
              ]
            }
            """
        ),
        f"include/{native_name}/service_core.h": _strip(
            f"""
            #pragma once

            #include <string>
            #include <string_view>

            namespace {native_name} {{

            inline constexpr const char* kProductName = "{cpp_title}";

            struct ServiceTick {{
                int heartbeat;
                std::string message;
            }};

            int normalize_interval_seconds(int requested_seconds);
            ServiceTick next_tick(std::string_view service_name, int previous_heartbeat);

            }}
            """
        ),
        "src/service_core.cpp": _strip(
            f"""
            #include "{native_name}/service_core.h"

            #include <algorithm>
            #include <sstream>

            namespace {native_name} {{

            int normalize_interval_seconds(int requested_seconds)
            {{
                return std::clamp(requested_seconds, 1, 300);
            }}

            ServiceTick next_tick(std::string_view service_name, int previous_heartbeat)
            {{
                ServiceTick tick{{previous_heartbeat + 1, {{}}}};
                std::ostringstream message;
                message << service_name << " heartbeat " << tick.heartbeat;
                tick.message = message.str();
                return tick;
            }}

            }}
            """
        ),
        "src/service_main.cpp": _strip(
            f"""
            #include "{native_name}/service_core.h"

            #include <atomic>
            #include <chrono>
            #include <iostream>
            #include <string>
            #include <thread>

            #if defined(_WIN32)
            #include <windows.h>

            namespace {{

            constexpr const wchar_t* kServiceName = L"{service_name_wide}";
            constexpr const wchar_t* kDisplayName = L"{display_name_wide}";

            std::atomic_bool g_stop_requested{{false}};
            SERVICE_STATUS_HANDLE g_status_handle = nullptr;
            SERVICE_STATUS g_status{{}};

            void log_line(const std::string& message)
            {{
                std::cout << message << std::endl;
                OutputDebugStringA((message + "\\n").c_str());
            }}

            void set_service_status(DWORD state, DWORD exit_code = NO_ERROR, DWORD wait_hint = 0)
            {{
                if (g_status_handle == nullptr) {{
                    return;
                }}

                static DWORD checkpoint = 1;
                g_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS;
                g_status.dwCurrentState = state;
                g_status.dwControlsAccepted =
                    state == SERVICE_RUNNING ? (SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN) : 0;
                g_status.dwWin32ExitCode = exit_code;
                g_status.dwServiceSpecificExitCode = 0;
                g_status.dwWaitHint = wait_hint;
                g_status.dwCheckPoint =
                    (state == SERVICE_RUNNING || state == SERVICE_STOPPED) ? 0 : checkpoint++;
                SetServiceStatus(g_status_handle, &g_status);
            }}

            int run_worker_loop(bool console_mode)
            {{
                int heartbeat = 0;
                const int interval = {native_name}::normalize_interval_seconds(1);
                while (!g_stop_requested.load()) {{
                    auto tick = {native_name}::next_tick("{cpp_title}", heartbeat);
                    heartbeat = tick.heartbeat;
                    log_line(tick.message);
                    if (console_mode && heartbeat >= 3) {{
                        break;
                    }}
                    std::this_thread::sleep_for(std::chrono::seconds(interval));
                }}
                return 0;
            }}

            void WINAPI control_handler(DWORD control)
            {{
                switch (control) {{
                case SERVICE_CONTROL_STOP:
                case SERVICE_CONTROL_SHUTDOWN:
                    g_stop_requested.store(true);
                    set_service_status(SERVICE_STOP_PENDING, NO_ERROR, 1000);
                    break;
                default:
                    break;
                }}
            }}

            void WINAPI service_main(DWORD, LPWSTR*)
            {{
                g_status_handle = RegisterServiceCtrlHandlerW(kServiceName, control_handler);
                if (g_status_handle == nullptr) {{
                    return;
                }}

                set_service_status(SERVICE_START_PENDING, NO_ERROR, 1000);
                g_stop_requested.store(false);
                set_service_status(SERVICE_RUNNING);
                run_worker_loop(false);
                set_service_status(SERVICE_STOPPED);
            }}

            std::wstring current_executable()
            {{
                std::wstring buffer(MAX_PATH, L'\\0');
                DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
                if (length == 0) {{
                    return {{}};
                }}
                buffer.resize(length);
                return buffer;
            }}

            DWORD install_service()
            {{
                SC_HANDLE manager = OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CREATE_SERVICE);
                if (manager == nullptr) {{
                    return GetLastError();
                }}

                std::wstring command = L"\\"" + current_executable() + L"\\"";
                SC_HANDLE service = CreateServiceW(
                    manager,
                    kServiceName,
                    kDisplayName,
                    SERVICE_ALL_ACCESS,
                    SERVICE_WIN32_OWN_PROCESS,
                    SERVICE_DEMAND_START,
                    SERVICE_ERROR_NORMAL,
                    command.c_str(),
                    nullptr,
                    nullptr,
                    nullptr,
                    nullptr,
                    nullptr);

                if (service == nullptr) {{
                    DWORD error = GetLastError();
                    CloseServiceHandle(manager);
                    return error == ERROR_SERVICE_EXISTS ? ERROR_SUCCESS : error;
                }}

                CloseServiceHandle(service);
                CloseServiceHandle(manager);
                return ERROR_SUCCESS;
            }}

            DWORD uninstall_service()
            {{
                SC_HANDLE manager = OpenSCManagerW(nullptr, nullptr, SC_MANAGER_CONNECT);
                if (manager == nullptr) {{
                    return GetLastError();
                }}

                SC_HANDLE service = OpenServiceW(manager, kServiceName, DELETE | SERVICE_STOP | SERVICE_QUERY_STATUS);
                if (service == nullptr) {{
                    DWORD error = GetLastError();
                    CloseServiceHandle(manager);
                    return error == ERROR_SERVICE_DOES_NOT_EXIST ? ERROR_SUCCESS : error;
                }}

                SERVICE_STATUS status{{}};
                ControlService(service, SERVICE_CONTROL_STOP, &status);
                DWORD error = DeleteService(service) ? ERROR_SUCCESS : GetLastError();
                CloseServiceHandle(service);
                CloseServiceHandle(manager);
                return error;
            }}

            int run_service_dispatcher()
            {{
                SERVICE_TABLE_ENTRYW table[] = {{
                    {{const_cast<LPWSTR>(kServiceName), service_main}},
                    {{nullptr, nullptr}},
                }};
                if (StartServiceCtrlDispatcherW(table)) {{
                    return 0;
                }}
                DWORD error = GetLastError();
                if (error == ERROR_FAILED_SERVICE_CONTROLLER_CONNECT) {{
                    return run_worker_loop(true);
                }}
                std::cerr << "StartServiceCtrlDispatcher failed with error " << error << std::endl;
                return 1;
            }}

            }}

            int main(int argc, char** argv)
            {{
                if (argc > 1) {{
                    const std::string command = argv[1];
                    if (command == "--console") {{
                        return run_worker_loop(true);
                    }}
                    if (command == "--install") {{
                        DWORD error = install_service();
                        if (error != ERROR_SUCCESS) {{
                            std::cerr << "Install failed with error " << error << std::endl;
                            return 1;
                        }}
                        std::cout << "Service installed: {service_symbol}" << std::endl;
                        return 0;
                    }}
                    if (command == "--uninstall") {{
                        DWORD error = uninstall_service();
                        if (error != ERROR_SUCCESS) {{
                            std::cerr << "Uninstall failed with error " << error << std::endl;
                            return 1;
                        }}
                        std::cout << "Service removed: {service_symbol}" << std::endl;
                        return 0;
                    }}
                }}

                return run_service_dispatcher();
            }}

            #else

            int main()
            {{
                int heartbeat = 0;
                for (int index = 0; index < 3; ++index) {{
                    auto tick = {native_name}::next_tick("{cpp_title}", heartbeat);
                    heartbeat = tick.heartbeat;
                    std::cout << tick.message << std::endl;
                }}
                return heartbeat == 3 ? 0 : 1;
            }}

            #endif
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include <cassert>
            #include <string>

            #include "{native_name}/service_core.h"

            int main()
            {{
                assert({native_name}::normalize_interval_seconds(-4) == 1);
                assert({native_name}::normalize_interval_seconds(500) == 300);

                auto first = {native_name}::next_tick("SmokeService", 0);
                assert(first.heartbeat == 1);
                assert(first.message.find("SmokeService") != std::string::npos);

                auto second = {native_name}::next_tick("SmokeService", first.heartbeat);
                assert(second.heartbeat == 2);
                return 0;
            }}
            """
        ),
        "build.py": _strip(
            """
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True)
                return completed.returncode


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake was not found on PATH. Install CMake 3.20+ and rerun this script.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                code = run(["cmake", "-S", ".", "-B", "build", "-DBUILD_TESTING=ON", *generator])
                if code != 0:
                    return code

                code = run(["cmake", "--build", "build", "--config", "Release"])
                if code != 0:
                    return code

                return run(["ctest", "--test-dir", "build", "-C", "Release", "--output-on-failure"])


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            .vs
            .vscode
            *.user
            *.obj
            *.pdb
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Native C++ Windows service scaffold generated by Aegis Project Builder.

            ## What It Includes

            - `src/service_main.cpp` with a Win32 service entry point, console fallback, and install/uninstall commands.
            - `src/service_core.cpp` and `include/{native_name}/service_core.h` with testable service logic.
            - `tests/smoke.cpp` validating core service behavior without installing the service.
            - `build.py` that configures, builds, and runs CTest through CMake.

            ## Build And Validate

            ```powershell
            python build.py
            ```

            ## Run In Console Mode

            ```powershell
            .\\build\\Release\\{native_name}.exe --console
            ```

            ## Install Or Remove The Service

            Run an elevated terminal before installing or removing Windows services.

            ```powershell
            .\\build\\Release\\{native_name}.exe --install
            .\\build\\Release\\{native_name}.exe --uninstall
            ```
            """
        ),
    }


def cpp_windows_internals_hooking_template(project_name: str) -> dict[str, str]:
    native_name = _python_package_name(project_name)
    title = _title_from_name(project_name)
    return {
        "CMakeLists.txt": _strip(
            f"""
            cmake_minimum_required(VERSION 3.20)

            project({native_name} VERSION 0.1.0 LANGUAGES CXX)

            set(CMAKE_CXX_STANDARD 20)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)

            add_library(${{PROJECT_NAME}}_core
              src/instrumentation.cpp
            )
            target_include_directories(${{PROJECT_NAME}}_core PUBLIC include vendor/minhook_shim)
            target_compile_features(${{PROJECT_NAME}}_core PUBLIC cxx_std_20)

            if(WIN32)
              target_compile_definitions(${{PROJECT_NAME}}_core PUBLIC WIN32_LEAN_AND_MEAN NOMINMAX)
              target_link_libraries(${{PROJECT_NAME}}_core PUBLIC psapi)
            endif()

            add_executable(${{PROJECT_NAME}} src/main.cpp)
            target_link_libraries(${{PROJECT_NAME}} PRIVATE ${{PROJECT_NAME}}_core)

            include(CTest)
            if(BUILD_TESTING)
              add_executable(${{PROJECT_NAME}}_smoke tests/smoke.cpp)
              target_link_libraries(${{PROJECT_NAME}}_smoke PRIVATE ${{PROJECT_NAME}}_core)
              add_test(NAME smoke COMMAND ${{PROJECT_NAME}}_smoke)
            endif()
            """
        ),
        f"include/{native_name}/instrumentation.h": _strip(
            f"""
            #pragma once

            #include <cstddef>
            #include <cstdint>
            #include <string>
            #include <vector>

            namespace {native_name} {{

            struct ModuleInfo {{
                std::string name;
                std::string path;
                std::uintptr_t base_address{{0}};
                std::size_t image_size{{0}};
            }};

            struct HookPlan {{
                std::string target_module;
                std::string target_symbol;
                std::string replacement_symbol;
                bool enabled{{false}};
            }};

            class HookRegistry {{
            public:
                bool add_plan(HookPlan plan);
                bool set_enabled(const std::string& target_symbol, bool enabled);
                [[nodiscard]] const std::vector<HookPlan>& plans() const noexcept;
                [[nodiscard]] std::string summary() const;

            private:
                std::vector<HookPlan> plans_;
            }};

            std::vector<ModuleInfo> enumerate_current_process_modules();
            std::string describe_windows_internals_scope();

            }} // namespace {native_name}
            """
        ),
        f"include/{native_name}/minhook_adapter.h": _strip(
            f"""
            #pragma once

            #include <string>

            #include <MinHook.h>

            #include "{native_name}/instrumentation.h"

            namespace {native_name} {{

            enum class HookApplyResult {{
                ready,
                invalid_plan,
                invalid_address,
                backend_error,
            }};

            struct HookInstallPreview {{
                HookApplyResult result{{HookApplyResult::backend_error}};
                MH_STATUS backend_status{{MH_ERROR_NOT_INITIALIZED}};
                std::string message;

                [[nodiscard]] bool ok() const noexcept
                {{
                    return result == HookApplyResult::ready && backend_status == MH_OK;
                }}
            }};

            class MinHookAdapter {{
            public:
                HookApplyResult validate_plan(const HookPlan& plan) const
                {{
                    if (plan.target_module.empty() || plan.target_symbol.empty() || plan.replacement_symbol.empty())
                    {{
                        return HookApplyResult::invalid_plan;
                    }}
                    return HookApplyResult::ready;
                }}

                HookInstallPreview install_preview(
                    const HookPlan& plan,
                    void* target_address,
                    void* replacement_address,
                    void** original_address) const
                {{
                    const HookApplyResult plan_result = validate_plan(plan);
                    if (plan_result != HookApplyResult::ready)
                    {{
                        return HookInstallPreview{{plan_result, MH_ERROR_INVALID_PARAMETER, "Invalid hook plan."}};
                    }}
                    if (target_address == nullptr || replacement_address == nullptr)
                    {{
                        return HookInstallPreview{{HookApplyResult::invalid_address, MH_ERROR_INVALID_PARAMETER, "Target and replacement addresses are required."}};
                    }}

                    MH_STATUS status = MH_Initialize();
                    if (status != MH_OK && status != MH_ERROR_ALREADY_INITIALIZED)
                    {{
                        return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                    }}
                    status = MH_CreateHook(target_address, replacement_address, original_address);
                    if (status != MH_OK)
                    {{
                        return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                    }}
                    status = MH_EnableHook(target_address);
                    if (status != MH_OK)
                    {{
                        return HookInstallPreview{{HookApplyResult::backend_error, status, MH_StatusToString(status)}};
                    }}
                    return HookInstallPreview{{HookApplyResult::ready, MH_OK, "Hook preview validated through MinHook-compatible API boundary."}};
                }}

                const char* backend_name() const noexcept
                {{
                    return "MinHook API-compatible adapter";
                }}
            }};

            }} // namespace {native_name}
            """
        ),
        "src/instrumentation.cpp": _strip(
            f"""
            #include "{native_name}/instrumentation.h"

            #include <algorithm>
            #include <sstream>
            #include <utility>

            #if defined(_WIN32)
            #include <windows.h>
            #include <psapi.h>
            #endif

            namespace {native_name} {{

            bool HookRegistry::add_plan(HookPlan plan)
            {{
                if (plan.target_module.empty() || plan.target_symbol.empty() || plan.replacement_symbol.empty())
                {{
                    return false;
                }}
                const auto duplicate = std::find_if(plans_.begin(), plans_.end(), [&](const HookPlan& existing) {{
                    return existing.target_module == plan.target_module && existing.target_symbol == plan.target_symbol;
                }});
                if (duplicate != plans_.end())
                {{
                    return false;
                }}
                plans_.push_back(std::move(plan));
                return true;
            }}

            bool HookRegistry::set_enabled(const std::string& target_symbol, bool enabled)
            {{
                for (HookPlan& plan : plans_)
                {{
                    if (plan.target_symbol == target_symbol)
                    {{
                        plan.enabled = enabled;
                        return true;
                    }}
                }}
                return false;
            }}

            const std::vector<HookPlan>& HookRegistry::plans() const noexcept
            {{
                return plans_;
            }}

            std::string HookRegistry::summary() const
            {{
                std::size_t enabled = 0;
                for (const HookPlan& plan : plans_)
                {{
                    enabled += plan.enabled ? 1U : 0U;
                }}
                std::ostringstream stream;
                stream << "Hook plans=" << plans_.size() << " enabled=" << enabled;
                return stream.str();
            }}

            std::vector<ModuleInfo> enumerate_current_process_modules()
            {{
                std::vector<ModuleInfo> modules;
            #if defined(_WIN32)
                HMODULE handles[1024]{{}};
                DWORD needed = 0;
                HANDLE process = GetCurrentProcess();
                if (EnumProcessModules(process, handles, sizeof(handles), &needed))
                {{
                    const std::size_t count = needed / sizeof(HMODULE);
                    for (std::size_t index = 0; index < count; ++index)
                    {{
                        char path[MAX_PATH]{{}};
                        MODULEINFO info{{}};
                        GetModuleFileNameExA(process, handles[index], path, MAX_PATH);
                        GetModuleInformation(process, handles[index], &info, sizeof(info));
                        ModuleInfo module;
                        module.path = path;
                        const auto slash = module.path.find_last_of("\\\\/");
                        module.name = slash == std::string::npos ? module.path : module.path.substr(slash + 1);
                        module.base_address = reinterpret_cast<std::uintptr_t>(info.lpBaseOfDll);
                        module.image_size = static_cast<std::size_t>(info.SizeOfImage);
                        modules.push_back(std::move(module));
                    }}
                }}
            #else
                modules.push_back(ModuleInfo{{"current-process", "portable-validation-stub", 0, 0}});
            #endif
                return modules;
            }}

            std::string describe_windows_internals_scope()
            {{
                return "Windows internals scaffold: modules, exported symbols, diagnostics, and authorized MinHook-style instrumentation boundaries.";
            }}

            }} // namespace {native_name}
            """
        ),
        "src/main.cpp": _strip(
            f"""
            #include <iostream>
            #include <string>

            #include "{native_name}/instrumentation.h"
            #include "{native_name}/minhook_adapter.h"

            namespace {{
            int observed_create_file_stub()
            {{
                return 7;
            }}

            int replacement_create_file_stub()
            {{
                return 8;
            }}
            }} // namespace

            int main(int argc, char** argv)
            {{
                const bool validate = argc > 1 && std::string(argv[1]) == "--aegis-validate";

                {native_name}::HookRegistry registry;
                registry.add_plan({native_name}::HookPlan{{"kernel32.dll", "CreateFileW", "ObservedCreateFileW", false}});
                registry.set_enabled("CreateFileW", true);

                {native_name}::MinHookAdapter adapter;
                void* original = nullptr;
                const auto install = adapter.install_preview(
                    registry.plans().front(),
                    reinterpret_cast<void*>(&observed_create_file_stub),
                    reinterpret_cast<void*>(&replacement_create_file_stub),
                    &original);
                const auto modules = {native_name}::enumerate_current_process_modules();

                std::cout << "{title} Windows internals tool\\n";
                std::cout << {native_name}::describe_windows_internals_scope() << "\\n";
                std::cout << registry.summary() << "\\n";
                std::cout << "Modules observed=" << modules.size() << "\\n";
                std::cout << "Hook backend=" << adapter.backend_name() << "\\n";
                std::cout << "Hook preview=" << install.message << "\\n";

                if (!install.ok() || original == nullptr || modules.empty())
                {{
                    std::cerr << "Instrumentation validation failed.\\n";
                    return 2;
                }}

                if (!validate)
                {{
                    std::cout << "Press Enter to close...";
                    std::string line;
                    std::getline(std::cin, line);
                }}
                return 0;
            }}
            """
        ),
        "tests/smoke.cpp": _strip(
            f"""
            #include <string>

            #include "{native_name}/instrumentation.h"
            #include "{native_name}/minhook_adapter.h"

            namespace {{
            int target_stub()
            {{
                return 1;
            }}

            int replacement_stub()
            {{
                return 2;
            }}
            }} // namespace

            int main()
            {{
                {native_name}::HookRegistry registry;
                if (!registry.add_plan({native_name}::HookPlan{{"user32.dll", "MessageBoxW", "ObservedMessageBoxW", false}}))
                {{
                    return 1;
                }}
                if (registry.add_plan({native_name}::HookPlan{{"user32.dll", "MessageBoxW", "OtherMessageBoxW", false}}))
                {{
                    return 2;
                }}
                if (!registry.set_enabled("MessageBoxW", true))
                {{
                    return 3;
                }}

                {native_name}::MinHookAdapter adapter;
                if (adapter.validate_plan(registry.plans().front()) != {native_name}::HookApplyResult::ready)
                {{
                    return 4;
                }}
                void* original = nullptr;
                const auto preview = adapter.install_preview(
                    registry.plans().front(),
                    reinterpret_cast<void*>(&target_stub),
                    reinterpret_cast<void*>(&replacement_stub),
                    &original);
                if (!preview.ok() || original == nullptr)
                {{
                    return 7;
                }}
                if (registry.summary().find("enabled=1") == std::string::npos)
                {{
                    return 5;
                }}
                return {native_name}::enumerate_current_process_modules().empty() ? 6 : 0;
            }}
            """
        ),
        "vendor/minhook_shim/MinHook.h": _strip(
            """
            #pragma once

            #ifdef __cplusplus
            extern "C" {
            #endif

            typedef enum MH_STATUS {
                MH_OK = 0,
                MH_ERROR_ALREADY_INITIALIZED = 1,
                MH_ERROR_NOT_INITIALIZED = 2,
                MH_ERROR_INVALID_PARAMETER = 3,
            } MH_STATUS;

            #define MH_ALL_HOOKS ((void*)0)

            static inline const char* MH_StatusToString(MH_STATUS status)
            {
                switch (status)
                {
                case MH_OK:
                    return "MH_OK";
                case MH_ERROR_ALREADY_INITIALIZED:
                    return "MH_ERROR_ALREADY_INITIALIZED";
                case MH_ERROR_NOT_INITIALIZED:
                    return "MH_ERROR_NOT_INITIALIZED";
                case MH_ERROR_INVALID_PARAMETER:
                    return "MH_ERROR_INVALID_PARAMETER";
                default:
                    return "MH_UNKNOWN";
                }
            }

            static inline MH_STATUS MH_Initialize(void)
            {
                return MH_OK;
            }

            static inline MH_STATUS MH_Uninitialize(void)
            {
                return MH_OK;
            }

            static inline MH_STATUS MH_CreateHook(void* target, void* detour, void** original)
            {
                if (target == 0 || detour == 0)
                {
                    return MH_ERROR_INVALID_PARAMETER;
                }
                if (original != 0)
                {
                    *original = target;
                }
                return MH_OK;
            }

            static inline MH_STATUS MH_EnableHook(void* target)
            {
                return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
            }

            static inline MH_STATUS MH_DisableHook(void* target)
            {
                return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
            }

            static inline MH_STATUS MH_RemoveHook(void* target)
            {
                return target == 0 ? MH_ERROR_INVALID_PARAMETER : MH_OK;
            }

            #ifdef __cplusplus
            }
            #endif
            """
        ),
        "build.py": _strip(
            f"""
            from __future__ import annotations

            import hashlib
            import os
            import shutil
            import subprocess
            import sys
            import tempfile
            from pathlib import Path


            ROOT = Path(__file__).resolve().parent
            APP_NAME = "{native_name}"
            BUILD_DIR = Path(
                os.environ.get(
                    "AEGIS_CMAKE_BUILD_DIR",
                    Path(tempfile.gettempdir()) / "aegis-cmake" / f"{{APP_NAME}}-{{hashlib.sha1(str(ROOT).encode('utf-8')).hexdigest()[:12]}}",
                )
            )


            def run(command: list[str]) -> int:
                print("Running:", " ".join(command))
                completed = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                return completed.returncode


            def find_app_executable() -> Path | None:
                names = {{APP_NAME, APP_NAME + ".exe"}}
                for candidate in BUILD_DIR.rglob("*"):
                    if candidate.is_file() and candidate.name in names:
                        return candidate
                return None


            def run_generated_app() -> int:
                app = find_app_executable()
                if app is None:
                    print("Generated Windows internals executable was not found under the CMake build directory.", file=sys.stderr)
                    return 3
                completed = subprocess.run([str(app), "--aegis-validate"], cwd=str(ROOT), text=True, capture_output=True)
                if completed.stdout:
                    print(completed.stdout, end="")
                if completed.stderr:
                    print(completed.stderr, end="", file=sys.stderr)
                if completed.returncode != 0:
                    return completed.returncode
                if "Windows internals tool" not in completed.stdout:
                    print("Expected Windows internals validation output was not found.", file=sys.stderr)
                    return 4
                return 0


            def main() -> int:
                if shutil.which("cmake") is None:
                    print("CMake 3.20+ is required to validate this Windows internals scaffold.", file=sys.stderr)
                    return 2

                generator = ["-G", "Ninja"] if os.name != "nt" and shutil.which("ninja") else []
                code = run(["cmake", "-S", ".", "-B", str(BUILD_DIR), "-DBUILD_TESTING=ON", *generator])
                if code != 0:
                    return code

                code = run(["cmake", "--build", str(BUILD_DIR), "--config", "Release"])
                if code != 0:
                    return code

                code = run(["ctest", "--test-dir", str(BUILD_DIR), "-C", "Release", "--output-on-failure"])
                if code != 0:
                    return code

                return run_generated_app()


            if __name__ == "__main__":
                raise SystemExit(main())
            """
        ),
        ".gitignore": _strip(
            """
            build
            out
            .vs
            .vscode
            *.user
            *.obj
            *.pdb
            *.exe
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            C++20 Windows internals and authorized instrumentation scaffold.

            ## Included

            - Current-process module enumeration through Win32/PSAPI when built on Windows.
            - A `HookRegistry` for planning, toggling, and validating hook definitions.
            - A `MinHookAdapter` boundary with an embedded `vendor/minhook_shim/MinHook.h` API-compatible validation shim.
            - CMake validation and smoke tests that do not patch memory or require elevated privileges.

            ## Validate

            ```powershell
            python build.py
            ```

            ## Notes

            This scaffold is for your own applications, diagnostics, modding APIs, internal tooling,
            and authorized research. Keep real hook installation isolated behind `MinHookAdapter`,
            add explicit process/module allow-lists, and record every active hook in the registry.
            Replace `vendor/minhook_shim` with the official MinHook source when you are ready to link real hooks.
            """
        ),
    }


def _python_package_name(project_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", project_name.replace("-", "_")).strip("_").lower()
    if not cleaned:
        return "aegis_app"
    if cleaned[0].isdigit():
        cleaned = f"app_{cleaned}"
    return cleaned


def _strip(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _title_from_name(project_name: str) -> str:
    return scaffold_title_from_name(project_name)
