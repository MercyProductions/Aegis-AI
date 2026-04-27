#include "Json.h"

#include <cmath>
#include <cctype>
#include <sstream>

namespace aegis {
namespace {

const JsonValue kNullValue{};

void AppendUtf8(std::string& out, unsigned codepoint)
{
    if (codepoint <= 0x7F) {
        out.push_back(static_cast<char>(codepoint));
    } else if (codepoint <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | ((codepoint >> 6) & 0x1F)));
        out.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xE0 | ((codepoint >> 12) & 0x0F)));
        out.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (codepoint & 0x3F)));
    }
}

int HexDigit(char c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F') {
        return c - 'A' + 10;
    }
    return -1;
}

class Parser {
public:
    explicit Parser(const std::string& input) : text_(input) {}

    JsonParseResult Parse()
    {
        JsonParseResult result;
        SkipWhitespace();
        result.value = ParseValue();
        if (!error_.empty()) {
            result.error = error_;
            return result;
        }

        SkipWhitespace();
        if (pos_ != text_.size()) {
            Fail("Unexpected trailing JSON content.");
            result.error = error_;
            return result;
        }

        result.ok = true;
        return result;
    }

private:
    const std::string& text_;
    size_t pos_ = 0;
    std::string error_;

    void Fail(const std::string& message)
    {
        if (!error_.empty()) {
            return;
        }
        std::ostringstream stream;
        stream << message << " Offset " << pos_ << ".";
        error_ = stream.str();
    }

    void SkipWhitespace()
    {
        while (pos_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[pos_])) != 0) {
            ++pos_;
        }
    }

    bool Consume(char expected)
    {
        SkipWhitespace();
        if (pos_ < text_.size() && text_[pos_] == expected) {
            ++pos_;
            return true;
        }
        return false;
    }

    bool ConsumeLiteral(const char* literal)
    {
        const size_t start = pos_;
        for (const char* cursor = literal; *cursor != '\0'; ++cursor) {
            if (pos_ >= text_.size() || text_[pos_] != *cursor) {
                pos_ = start;
                return false;
            }
            ++pos_;
        }
        return true;
    }

    JsonValue ParseValue()
    {
        SkipWhitespace();
        if (pos_ >= text_.size()) {
            Fail("Unexpected end of JSON.");
            return {};
        }

        const char c = text_[pos_];
        if (c == '"') {
            return ParseString();
        }
        if (c == '{') {
            return ParseObject();
        }
        if (c == '[') {
            return ParseArray();
        }
        if (c == '-' || (c >= '0' && c <= '9')) {
            return ParseNumber();
        }
        if (ConsumeLiteral("true")) {
            JsonValue value;
            value.type = JsonValue::Type::Bool;
            value.bool_value = true;
            return value;
        }
        if (ConsumeLiteral("false")) {
            JsonValue value;
            value.type = JsonValue::Type::Bool;
            value.bool_value = false;
            return value;
        }
        if (ConsumeLiteral("null")) {
            return {};
        }

        Fail("Unexpected JSON token.");
        return {};
    }

    JsonValue ParseString()
    {
        JsonValue value;
        value.type = JsonValue::Type::String;

        if (pos_ >= text_.size() || text_[pos_] != '"') {
            Fail("Expected string.");
            return value;
        }

        ++pos_;
        while (pos_ < text_.size()) {
            const char c = text_[pos_++];
            if (c == '"') {
                return value;
            }
            if (c != '\\') {
                value.string_value.push_back(c);
                continue;
            }

            if (pos_ >= text_.size()) {
                Fail("Unterminated string escape.");
                return value;
            }

            const char esc = text_[pos_++];
            switch (esc) {
            case '"': value.string_value.push_back('"'); break;
            case '\\': value.string_value.push_back('\\'); break;
            case '/': value.string_value.push_back('/'); break;
            case 'b': value.string_value.push_back('\b'); break;
            case 'f': value.string_value.push_back('\f'); break;
            case 'n': value.string_value.push_back('\n'); break;
            case 'r': value.string_value.push_back('\r'); break;
            case 't': value.string_value.push_back('\t'); break;
            case 'u':
            {
                if (pos_ + 4 > text_.size()) {
                    Fail("Short unicode escape.");
                    return value;
                }
                unsigned codepoint = 0;
                for (int i = 0; i < 4; ++i) {
                    const int digit = HexDigit(text_[pos_++]);
                    if (digit < 0) {
                        Fail("Invalid unicode escape.");
                        return value;
                    }
                    codepoint = (codepoint << 4) | static_cast<unsigned>(digit);
                }
                AppendUtf8(value.string_value, codepoint);
                break;
            }
            default:
                Fail("Invalid string escape.");
                return value;
            }
        }

        Fail("Unterminated string.");
        return value;
    }

    JsonValue ParseNumber()
    {
        const size_t start = pos_;
        if (text_[pos_] == '-') {
            ++pos_;
        }
        while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_])) != 0) {
            ++pos_;
        }
        if (pos_ < text_.size() && text_[pos_] == '.') {
            ++pos_;
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_])) != 0) {
                ++pos_;
            }
        }
        if (pos_ < text_.size() && (text_[pos_] == 'e' || text_[pos_] == 'E')) {
            ++pos_;
            if (pos_ < text_.size() && (text_[pos_] == '+' || text_[pos_] == '-')) {
                ++pos_;
            }
            while (pos_ < text_.size() && std::isdigit(static_cast<unsigned char>(text_[pos_])) != 0) {
                ++pos_;
            }
        }

        JsonValue value;
        value.type = JsonValue::Type::Number;
        try {
            value.number_value = std::stod(text_.substr(start, pos_ - start));
        } catch (...) {
            Fail("Invalid number.");
        }
        return value;
    }

    JsonValue ParseArray()
    {
        JsonValue value;
        value.type = JsonValue::Type::Array;
        ++pos_;
        SkipWhitespace();
        if (Consume(']')) {
            return value;
        }

        while (pos_ < text_.size()) {
            value.array_value.push_back(ParseValue());
            if (!error_.empty()) {
                return value;
            }
            if (Consume(']')) {
                return value;
            }
            if (!Consume(',')) {
                Fail("Expected comma in array.");
                return value;
            }
        }

        Fail("Unterminated array.");
        return value;
    }

    JsonValue ParseObject()
    {
        JsonValue value;
        value.type = JsonValue::Type::Object;
        ++pos_;
        SkipWhitespace();
        if (Consume('}')) {
            return value;
        }

        while (pos_ < text_.size()) {
            JsonValue key = ParseString();
            if (!error_.empty()) {
                return value;
            }
            if (!Consume(':')) {
                Fail("Expected colon in object.");
                return value;
            }
            value.object_value[key.string_value] = ParseValue();
            if (!error_.empty()) {
                return value;
            }
            if (Consume('}')) {
                return value;
            }
            if (!Consume(',')) {
                Fail("Expected comma in object.");
                return value;
            }
        }

        Fail("Unterminated object.");
        return value;
    }
};

}

const JsonValue& JsonValue::operator[](const std::string& key) const
{
    if (type != Type::Object) {
        return kNullValue;
    }
    const auto it = object_value.find(key);
    return it == object_value.end() ? kNullValue : it->second;
}

const JsonValue& JsonValue::At(size_t index) const
{
    if (type != Type::Array || index >= array_value.size()) {
        return kNullValue;
    }
    return array_value[index];
}

bool JsonValue::Has(const std::string& key) const
{
    return type == Type::Object && object_value.find(key) != object_value.end();
}

std::string JsonValue::AsString(const std::string& fallback) const
{
    if (type == Type::String) {
        return string_value;
    }
    if (type == Type::Number) {
        if (std::fabs(number_value - std::round(number_value)) < 0.0001) {
            return std::to_string(static_cast<long long>(std::llround(number_value)));
        }
        std::ostringstream stream;
        stream << number_value;
        return stream.str();
    }
    if (type == Type::Bool) {
        return bool_value ? "true" : "false";
    }
    return fallback;
}

int JsonValue::AsInt(int fallback) const
{
    if (type == Type::Number) {
        return static_cast<int>(std::llround(number_value));
    }
    if (type == Type::String) {
        try {
            return std::stoi(string_value);
        } catch (...) {
            return fallback;
        }
    }
    return fallback;
}

double JsonValue::AsDouble(double fallback) const
{
    if (type == Type::Number) {
        return number_value;
    }
    if (type == Type::String) {
        try {
            return std::stod(string_value);
        } catch (...) {
            return fallback;
        }
    }
    return fallback;
}

bool JsonValue::AsBool(bool fallback) const
{
    if (type == Type::Bool) {
        return bool_value;
    }
    if (type == Type::Number) {
        return number_value != 0.0;
    }
    if (type == Type::String) {
        return string_value == "true" || string_value == "1";
    }
    return fallback;
}

JsonParseResult ParseJson(const std::string& text)
{
    return Parser(text).Parse();
}

}
