from app.utils.text_cleaner import clean_text


NEWS_CREDIBILITY_PROMPT_TYPE = "news_credibility"

NEWS_CREDIBILITY_PLACEHOLDER_GROUPS = (
    (
        "新闻标题",
        ("{title}",),
        "新闻检测Prompt必须包含新闻标题占位符：{title}",
    ),
    (
        "新闻正文",
        ("{content}",),
        "新闻检测Prompt必须包含新闻正文占位符：{content}",
    ),
    (
        "检索证据",
        ("{evidence_list}", "{evidence_json}"),
        "新闻检测Prompt必须包含检索证据占位符：{evidence_list}（兼容 {evidence_json}）",
    ),
)


class PromptTemplateValidationError(ValueError):
    """Raised when a Prompt template cannot safely serve its declared type."""


def validate_prompt_template_content(prompt_type: str, content: str) -> str:
    """Validate and normalize a Prompt template using the rules for its type."""

    normalized_type = clean_text(prompt_type, max_length=50)
    normalized_content = clean_text(content, max_length=None)
    if not normalized_content:
        raise PromptTemplateValidationError("Prompt内容不能为空")

    if normalized_type != NEWS_CREDIBILITY_PROMPT_TYPE:
        return normalized_content

    errors = [
        error_message
        for _, placeholders, error_message in NEWS_CREDIBILITY_PLACEHOLDER_GROUPS
        if not any(placeholder in normalized_content for placeholder in placeholders)
    ]
    if errors:
        raise PromptTemplateValidationError("；".join(errors))

    return normalized_content
