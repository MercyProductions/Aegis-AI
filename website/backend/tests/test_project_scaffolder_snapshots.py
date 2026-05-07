from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aegis_ai.project_scaffolder import ProjectScaffolder


TEMPLATE_SNAPSHOTS: dict[str, dict[str, object]] = {
    "browser-extension-mv3": {
        "file_count": 12,
        "hashes": {
            ".gitignore": "484a1bd398828094a1c9df70a9b543eef9c700aaac31ad01cbe5d7d96f4ee471",
            "README.md": "66465f511ce675bc5cc7dbd345f3c5338d43a7af3571d1dc153b8dcee6c3709c",
            "build.py": "d16a7241331b8c6d5e8ff346de13449b374da62b9b363127486c4a5062f8463b",
            "manifest.json": "cc4ec3afc2c3653ecdca4004d50171154565ee9bfeeeaf896a6cba478a364f33",
            "options/options.css": "7780356381967498b7c41eecedd1d6803003219bd78aa9e1991b9ae66c8a5bb0",
            "options/options.html": "1839f3e391e7b982042907b2ad224cb462fe0342040d388d686af792fd9a84a5",
            "options/options.js": "c0e6f9f4a2678a4894e9e10e29a8671cb4aa531cd1da20cf1da4d52e782b8ef3",
            "popup/popup.css": "35e14a7db476a790ea39394191a7d22ec04e176509b27244dd7bd37cc7afc81c",
            "popup/popup.html": "ad67bfd5acc59f52bbb8f71072ae970ce62fa82946b0076541ff7ea5df3fc4fa",
            "popup/popup.js": "5d81a7523e2d96d7c68153c293367ce891885dbd5de544d447af981718d9546f",
            "src/background.js": "5ee60bb9e426154609a8a4cee2ea9806c50cc5633da7e4892b881fef4f22c6bb",
            "src/content.js": "be12a2359fa6a17857ad1963217698738957b34917d66b96bf44db4089cd789a",
        },
    },
    "cpp-cmake-cli": {
        "file_count": 7,
        "hashes": {
            ".gitignore": "408d594a942c02bc8746c1f3a7b27f6f8ffaed225c5ff907810914243bb04974",
            "CMakeLists.txt": "b329535bc2b6f0183ee18c7ec60660e7361dedfe398792368e91d0cca4e3681f",
            "README.md": "57ac718465335b4f0d4f0c1a1d540a9dc96744770d48efd0a6fabd256443f353",
            "build.py": "7525f13aba421ee8be86c488df0a8818ddf110d44f1588c872e6a46451514cf0",
            "include/golden_sample/version.h": "7543f188fab9485728c8f2785d001f58d1384fc5d2046d3f246d35c0711957e5",
            "src/main.cpp": "2308995414c56e3d23347ca5a7dac080e9a8a31721a527ef2bdb32c84c940953",
            "tests/smoke.cpp": "384548e64a02d5de44b818bb84a9500dc0ed48ef2926da191c29b5d8ea1f9b39",
        },
    },
    "dotnet-wpf-csharp": {
        "file_count": 11,
        "hashes": {
            ".gitignore": "f65a7d0703375e142f4683903461b1460e88a42f4e7787d595a00205a5fd7768",
            "README.md": "5a241e41a1b21994c2a8ba8d38ac65016e6e1625504db8cf9c952c234a96ed49",
            "build.py": "27050c1e9e78be1035de64db7b41abc64900a0708851121b577e2290fb7db3ba",
            "src/GoldenSample/App.xaml": "5f3a23c259f041ee558cbe5c57af41d005e637d5f6c8c57ffe6f3dd84bd23e0c",
            "src/GoldenSample/App.xaml.cs": "98733cd3d19b5c92f6eec01aeece89910d80a7b0a335019b9cdf4d3b730677af",
            "src/GoldenSample/DashboardState.cs": "ff4f38d25edffc1dd02152465d8c030b966c3af70a5827ba1a49cd759db907d5",
            "src/GoldenSample/GoldenSample.csproj": "4f2858e2b30bbe7b647bedd984fe43e9127f6d03b3d32fc6ee1e816cef118bcb",
            "src/GoldenSample/MainWindow.xaml": "9ccb0e1d7185eaf7907d0064686c602afebca2aff8dfe83545ad6cb7383a3573",
            "src/GoldenSample/MainWindow.xaml.cs": "45bb4a7e721f3add4572904eeedac09fad8bad3fdead3da78c3579e114df14c9",
            "tests/GoldenSample.Smoke/GoldenSample.Smoke.csproj": "1263b55e4a234a436afcf919f51ec79f4e2f1ce1799aa80d7a13b8a8ef0cdec3",
            "tests/GoldenSample.Smoke/Program.cs": "c106af00b117bd4920f80b125b49347cca41eb7d491c6f07fa83ed3829a38c61",
        },
    },
    "go-http-api": {
        "file_count": 6,
        "hashes": {
            ".gitignore": "1cda0030822c9cb19b8a1da4ca98047612308b087c050d783cf9e4d3d85f8e22",
            "README.md": "0b62c3bfb9648908490cf9143201073d902b0ed0fd42f4b6695764c07cb4a8ca",
            "cmd/server/main.go": "dda600487bb379bcdf1e7344c4ab0f934e3cf4ef6c25adaf71fcb5a53a5728e1",
            "go.mod": "8f0ca755a37170e9637f5bdf8f7255d9bcd814a7e983c0ba483513ec68d32ea9",
            "internal/api/router.go": "938f2fb3084a1719171b81e7503948628c2d81a2b3d2cc2bc99420c0fcd93262",
            "internal/api/router_test.go": "8aad2f9933997222c627d3eb0ca99099f52059fd953abb2d1160f4865adc3124",
        },
    },
    "python-cli": {
        "file_count": 7,
        "hashes": {
            ".gitignore": "3d74924c74c18d6c66908410110fae251246906b5741ef0817ffc1a7c76f3cc5",
            "README.md": "bb714a0ccf29b307684e815f6a2d535bd94c4ab961ee47ea4119ccde69797aff",
            "build.py": "3543bf17ebb9a106efb43b33d719398cc7f5ab8391d8fbc951bf7cab8659bffc",
            "pyproject.toml": "9ad4ee5e00802753bf0601233816c977115374eade545105fd4819d3c1f8225c",
            "src/golden_sample/__init__.py": "b576d15ec3b4344fd45759081e26534d0407d1f8f45362a8c7136eb2efe0ceb3",
            "src/golden_sample/main.py": "f839aa35f68b11ee45ea94fe4cbe87d63c8d2c5300a69109111453db437b3eee",
            "tests/test_smoke.py": "1c82ce8a1abea18409cd4037900fd180c7860608a6d642343174b937b47a7997",
        },
    },
    "rust-cli": {
        "file_count": 5,
        "hashes": {
            ".gitignore": "f9b1ca6ae27d1c18215265024629a8960c31379f206d9ed20f64e0b2dcf79805",
            "Cargo.toml": "05b820d424052815289769cdddefe9c69c00a6fd49e5b8feec938a5c45cab8cd",
            "README.md": "7bb3fe2d7bcbee9bcc8ea0291cdc8dcf2bccc5e2f97c93e3d4c845c03175d58b",
            "src/lib.rs": "6b0c0b5f4e374cd4600a218cd7cafdc994e31ae50c436f5ebee11c00ba7c2b77",
            "src/main.rs": "fa433a29c1999979d992d26a2e603fa363ca05774b25685b315fa6c7e95a5e80",
        },
    },
    "vite-react-ts": {
        "file_count": 9,
        "hashes": {
            ".gitignore": "62d50a03a4a6217cec6d7ef34fbcfb71309e911f83fed9bb3e6dabae3a3a0471",
            "README.md": "291a1642b72baa1df843790aed9fe98afbf7c056d3d89239841fcbcddb0e22c0",
            "index.html": "274c7d1d46ffaaa85a296bc298fa8928fc9d622df5ac96c20a7ee0ce4ec74d66",
            "package.json": "a6f0b187ed88df45a010c2a52d81bc52f8098d321d8c8bafe23b2a6b337db0bb",
            "src/App.tsx": "fa5054e50d8529d931e33805ab05cee5542d0c0d0e66f8108ef76fe74311ab90",
            "src/main.tsx": "525f0802ef08be2869cec123731c5f88eb83b8819863f27010edf0824ce7e5c5",
            "src/styles.css": "ed1091f5e77b92d7c1dd3d48df405b73bdb068c63ad65d5b49f93e1a9c2c5e88",
            "tsconfig.json": "9665597ba397119a137d724b8987ad6584f84a987aef5cd3d481ad52eedda218",
            "vite.config.ts": "c9f2b1d8adb74ccdf5b3279875524ab2f6c1dccf88474c85e96d02aec6964910",
        },
    },
}


class ProjectScaffolderSnapshotTests(unittest.TestCase):
    def test_representative_template_outputs_match_snapshots(self) -> None:
        for preset_id, snapshot in TEMPLATE_SNAPSHOTS.items():
            with self.subTest(preset_id=preset_id):
                files = ProjectScaffolder._template_for(preset_id)("golden-sample")
                hashes = {
                    path: hashlib.sha256(content.encode("utf-8")).hexdigest()
                    for path, content in sorted(files.items())
                }

                self.assertEqual(len(files), snapshot["file_count"])
                self.assertEqual(hashes, snapshot["hashes"])


if __name__ == "__main__":
    unittest.main()
