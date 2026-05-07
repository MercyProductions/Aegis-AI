from __future__ import annotations

import textwrap

from .project_scaffold_names import project_name as scaffold_project_name
from .project_scaffold_targets import title_from_name as scaffold_title_from_name


def electron_react_template(project_name: str) -> dict[str, str]:
    title = _title_from_name(project_name)
    package_name = _manifest_package_name(project_name)
    return {
        "package.json": _strip(
            f"""
            {{
              "name": "{package_name}",
              "version": "0.1.0",
              "private": true,
              "main": "dist/main/index.js",
              "scripts": {{
                "dev": "electron-vite dev",
                "build": "tsc --noEmit && electron-vite build",
                "preview": "electron-vite preview"
              }},
              "dependencies": {{
                "@vitejs/plugin-react": "^4.3.4",
                "react": "^19.0.0",
                "react-dom": "^19.0.0"
              }},
              "devDependencies": {{
                "@swc/core": "^1.15.32",
                "@types/node": "^22.10.1",
                "@types/react": "^19.0.1",
                "@types/react-dom": "^19.0.1",
                "electron": "^33.2.1",
                "electron-vite": "^5.0.0",
                "typescript": "^5.7.2",
                "vite": "^6.0.3"
              }}
            }}
            """
        ),
        "electron.vite.config.ts": _strip(
            """
            import { defineConfig, externalizeDepsPlugin } from 'electron-vite';
            import react from '@vitejs/plugin-react';

            export default defineConfig({
              main: {
                plugins: [externalizeDepsPlugin()]
              },
              preload: {
                plugins: [externalizeDepsPlugin()]
              },
              renderer: {
                plugins: [react()]
              }
            });
            """
        ),
        "tsconfig.json": _strip(
            """
            {
              "compilerOptions": {
                "target": "ES2022",
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "jsx": "react-jsx",
                "strict": true,
                "skipLibCheck": true,
                "isolatedModules": true,
                "types": ["node"]
              },
              "include": ["src/**/*.ts", "src/**/*.tsx", "electron.vite.config.ts"]
            }
            """
        ),
        "src/main/index.ts": _strip(
            """
            import { app, BrowserWindow } from 'electron';
            import { join } from 'node:path';

            const createWindow = () => {
              const win = new BrowserWindow({
                width: 1280,
                height: 820,
                minWidth: 960,
                minHeight: 680,
                backgroundColor: '#071018',
                webPreferences: {
                  preload: join(__dirname, '../preload/index.js'),
                  contextIsolation: true,
                  nodeIntegration: false
                }
              });

              if (process.env.ELECTRON_RENDERER_URL) {
                win.loadURL(process.env.ELECTRON_RENDERER_URL);
              } else {
                win.loadFile(join(__dirname, '../renderer/index.html'));
              }
            };

            app.whenReady().then(createWindow);
            app.on('window-all-closed', () => {
              if (process.platform !== 'darwin') app.quit();
            });
            """
        ),
        "src/preload/index.ts": _strip(
            """
            import { contextBridge } from 'electron';

            contextBridge.exposeInMainWorld('AegisDesktop', {
              platform: process.platform
            });
            """
        ),
        "src/renderer/index.html": _strip(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>{title}</title>
              </head>
              <body>
                <div id="root"></div>
                <script type="module" src="/src/main.tsx"></script>
              </body>
            </html>
            """
        ),
        "src/renderer/src/main.tsx": _strip(
            """
            import React from 'react';
            import { createRoot } from 'react-dom/client';
            import { App } from './App';
            import './styles.css';

            createRoot(document.getElementById('root')!).render(
              <React.StrictMode>
                <App />
              </React.StrictMode>
            );
            """
        ),
        "src/renderer/src/App.tsx": _strip(
            f"""
            const actions = ['Plan', 'Build', 'Validate', 'Ship'];

            export function App() {{
              return (
                <main className="shell">
                  <section className="hero">
                    <p className="eyebrow">Desktop workspace</p>
                    <h1>{title}</h1>
                    <p>Native-ready Electron shell with a secure preload bridge and React renderer.</p>
                  </section>
                  <section className="grid">
                    {{actions.map((action) => (
                      <article key={{action}}>
                        <span>{{action}}</span>
                        <p>Wire this lane to the app workflow you want Aegis to automate next.</p>
                      </article>
                    ))}}
                  </section>
                </main>
              );
            }}
            """
        ),
        "src/renderer/src/styles.css": _strip(
            """
            :root {
              color: #edf7f3;
              background: #071018;
              font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }

            body { margin: 0; min-height: 100vh; }
            .shell { min-height: 100vh; padding: 48px; background: radial-gradient(circle at top left, #123b35, transparent 34%), #071018; }
            .hero { max-width: 760px; }
            .eyebrow { color: #27de7d; text-transform: uppercase; font-size: 12px; letter-spacing: 0.08em; }
            h1 { font-size: 48px; margin: 8px 0 16px; }
            p { color: #aab7c4; line-height: 1.65; }
            .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 36px; }
            article { border: 1px solid #203040; border-radius: 8px; background: #0c1620; padding: 18px; }
            span { color: #27de7d; font-weight: 700; }
            @media (max-width: 860px) { .shell { padding: 28px; } .grid { grid-template-columns: 1fr; } h1 { font-size: 36px; } }
            """
        ),
        ".gitignore": _strip(
            """
            node_modules
            dist
            out
            *.log
            .env
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Electron React TypeScript desktop app generated by Aegis Project Builder.

            ```bash
            npm install
            npm run dev
            npm run build
            ```
            """
        ),
    }


def tauri_react_template(project_name: str) -> dict[str, str]:
    title = _title_from_name(project_name)
    package_name = _manifest_package_name(project_name)
    return {
        "package.json": _strip(
            f"""
            {{
              "name": "{package_name}",
              "version": "0.1.0",
              "private": true,
              "type": "module",
              "scripts": {{
                "dev": "tauri dev",
                "build": "vite build && tauri build",
                "web:dev": "vite",
                "web:build": "vite build"
              }},
              "dependencies": {{
                "@tauri-apps/api": "^2.2.0",
                "@vitejs/plugin-react": "^4.3.4",
                "react": "^19.0.0",
                "react-dom": "^19.0.0"
              }},
              "devDependencies": {{
                "@tauri-apps/cli": "^2.2.0",
                "@types/react": "^19.0.1",
                "@types/react-dom": "^19.0.1",
                "typescript": "^5.7.2",
                "vite": "^6.0.3"
              }}
            }}
            """
        ),
        "index.html": _strip(
            f"""
            <div id="root"></div>
            <script type="module" src="/src/main.tsx"></script>
            <title>{title}</title>
            """
        ),
        "src/main.tsx": _strip(
            """
            import React from 'react';
            import { createRoot } from 'react-dom/client';
            import { App } from './App';
            import './styles.css';

            createRoot(document.getElementById('root')!).render(
              <React.StrictMode>
                <App />
              </React.StrictMode>
            );
            """
        ),
        "src/App.tsx": _strip(
            f"""
            import {{ invoke }} from '@tauri-apps/api/core';

            export function App() {{
              async function greet() {{
                const response = await invoke<string>('greet', {{ name: 'Aegis' }});
                alert(response);
              }}

              return (
                <main className="shell">
                  <p className="eyebrow">Tauri workspace</p>
                  <h1>{title}</h1>
                  <p>Lightweight desktop app with a Rust host and React UI.</p>
                  <button onClick={{greet}}>Ping Rust Host</button>
                </main>
              );
            }}
            """
        ),
        "src/styles.css": _strip(
            """
            :root { background: #071018; color: #edf7f3; font-family: Inter, system-ui, sans-serif; }
            body { margin: 0; }
            .shell { min-height: 100vh; display: grid; align-content: center; gap: 18px; padding: 48px; }
            .eyebrow { color: #27de7d; font-size: 12px; font-weight: 800; text-transform: uppercase; }
            h1 { font-size: 48px; margin: 0; }
            p { color: #9aa8b6; max-width: 620px; line-height: 1.7; }
            button { width: fit-content; border: 0; border-radius: 8px; padding: 12px 16px; background: #27de7d; color: #071018; font-weight: 800; }
            """
        ),
        "tsconfig.json": _strip(
            """
            {
              "compilerOptions": {
                "target": "ES2022",
                "module": "ESNext",
                "moduleResolution": "Bundler",
                "jsx": "react-jsx",
                "strict": true,
                "skipLibCheck": true
              },
              "include": ["src"]
            }
            """
        ),
        "src-tauri/Cargo.toml": _strip(
            f"""
            [package]
            name = "{package_name}"
            version = "0.1.0"
            edition = "2021"

            [dependencies]
            tauri = {{ version = "2.2.0", features = [] }}
            tauri-build = "2.0.4"
            serde = {{ version = "1", features = ["derive"] }}
            serde_json = "1"

            [build-dependencies]
            tauri-build = "2.0.4"
            """
        ),
        "src-tauri/tauri.conf.json": _strip(
            f"""
            {{
              "$schema": "https://schema.tauri.app/config/2",
              "productName": "{title}",
              "version": "0.1.0",
              "identifier": "com.aegis.{project_name}",
              "build": {{
                "beforeDevCommand": "npm run web:dev",
                "devUrl": "http://localhost:5173",
                "beforeBuildCommand": "npm run web:build",
                "frontendDist": "../dist"
              }},
              "app": {{
                "windows": [{{ "title": "{title}", "width": 1200, "height": 780 }}]
              }}
            }}
            """
        ),
        "src-tauri/build.rs": _strip(
            """
            fn main() {
                tauri_build::build()
            }
            """
        ),
        "src-tauri/src/main.rs": _strip(
            """
            #[tauri::command]
            fn greet(name: &str) -> String {
                format!("Aegis host ready for {name}")
            }

            fn main() {
                tauri::Builder::default()
                    .invoke_handler(tauri::generate_handler![greet])
                    .run(tauri::generate_context!())
                    .expect("error while running tauri application");
            }
            """
        ),
        ".gitignore": _strip(
            """
            node_modules
            dist
            src-tauri/target
            .env
            """
        ),
        "README.md": _strip(
            f"""
            # {title}

            Tauri React TypeScript app generated by Aegis Project Builder.

            ```bash
            npm install
            npm run dev
            npm run build
            ```
            """
        ),
    }


def _manifest_package_name(project_name: str, fallback_prefix: str = "aegis") -> str:
    cleaned = scaffold_project_name(project_name)
    if cleaned[0].isdigit():
        cleaned = f"{fallback_prefix}-{cleaned}"
    return cleaned


def _strip(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def _title_from_name(project_name: str) -> str:
    return scaffold_title_from_name(project_name)
