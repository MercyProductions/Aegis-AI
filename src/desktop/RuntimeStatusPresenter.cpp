#include "desktop/RuntimeStatusPresenter.h"

#include <algorithm>
#include <cctype>

namespace aegis {
namespace {

std::string LowerAscii(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

std::string ValueOrUnknown(const std::string& value)
{
    return value.empty() ? "unknown" : value;
}

}  // namespace

RuntimeStatusTone RuntimeServiceTone(bool connected)
{
    return connected ? RuntimeStatusTone::Good : RuntimeStatusTone::Error;
}

std::string RuntimeServiceLabel(bool connected)
{
    return connected ? "Connected" : "Disconnected";
}

RuntimeStatusTone ReleaseCompatibilityTone(const std::string& status)
{
    const std::string normalized = LowerAscii(status);
    if (normalized == "blocked") {
        return RuntimeStatusTone::Error;
    }
    if (normalized == "warning" || normalized == "unavailable") {
        return RuntimeStatusTone::Warning;
    }
    return RuntimeStatusTone::Good;
}

ReleaseCompatibilityView BuildReleaseCompatibilityView(const DesktopRuntimeStatus& status)
{
    ReleaseCompatibilityView view;
    view.status_label = status.release_compatibility_status.empty() ? "not checked" : status.release_compatibility_status;
    view.status_tone = ReleaseCompatibilityTone(view.status_label);
    view.schema_label = ValueOrUnknown(status.release_schema_version);

    if (!status.release_required_core_version.empty() || !status.release_minimum_client_version.empty()) {
        view.requirements_label = "Release requires: Core " + ValueOrUnknown(status.release_required_core_version) +
            ", Desktop " + ValueOrUnknown(status.release_minimum_client_version);
    }

    if (!status.release_compatibility_blockers.empty()) {
        view.notice_label = "Compatibility blocker: " + status.release_compatibility_blockers.front();
        view.notice_tone = RuntimeStatusTone::Error;
    } else if (!status.release_compatibility_warnings.empty()) {
        view.notice_label = "Compatibility warning: " + status.release_compatibility_warnings.front();
        view.notice_tone = RuntimeStatusTone::Warning;
    } else if (!status.release_compatibility_recommendations.empty()) {
        view.notice_label = "Compatibility note: " + status.release_compatibility_recommendations.front();
        view.notice_tone = RuntimeStatusTone::Good;
    }

    return view;
}

}  // namespace aegis
