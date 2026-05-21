#pragma once

#include "AegisClient.h"

#include <string>

namespace aegis {

enum class RuntimeStatusTone {
    Good,
    Warning,
    Error
};

struct ReleaseCompatibilityView {
    std::string status_label;
    RuntimeStatusTone status_tone = RuntimeStatusTone::Good;
    std::string schema_label;
    std::string requirements_label;
    std::string notice_label;
    RuntimeStatusTone notice_tone = RuntimeStatusTone::Good;
};

RuntimeStatusTone RuntimeServiceTone(bool connected);
std::string RuntimeServiceLabel(bool connected);

RuntimeStatusTone ReleaseCompatibilityTone(const std::string& status);
ReleaseCompatibilityView BuildReleaseCompatibilityView(const DesktopRuntimeStatus& status);

}  // namespace aegis
