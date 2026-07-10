from __future__ import annotations

from datetime import datetime

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.knowledge_item import KnowledgeItem
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.schemas.knowledge import KnowledgeCreate
from app.services.knowledge_service import create_knowledge_item, update_knowledge_item
from app.services.prompt_template_validator import NEWS_CREDIBILITY_PROMPT_TYPE


DEMO_PASSWORD = "Chapter5Demo!2026"

USERS = [
    {
        "username": "chapter5_user",
        "email": "chapter5_user@example.com",
        "role": "user",
    },
    {
        "username": "chapter5_admin",
        "email": "chapter5_admin@example.com",
        "role": "admin",
    },
]

KNOWLEDGE_ROWS = [
    {
        "title": "第五章演示：气象部门发布台风蓝色预警",
        "content": (
            "气象部门发布台风蓝色预警时，会同时说明影响海域、陆地风雨范围、"
            "预计登陆时间和防御建议。公众应以国家或地方气象部门滚动通报为准，"
            "避免依据匿名截图判断灾害等级。"
        ),
        "category": "社会民生",
        "truth_label": "可信新闻",
        "source_name": "气象部门公开通报",
        "source_url": "https://example.com/chapter5/weather-warning",
        "publish_time": datetime(2026, 6, 20, 9, 30),
        "summary": "官方台风预警应包含影响范围、时间窗口和防御建议。",
        "keywords": "第五章演示,台风,气象预警,官方通报",
        "debunking_explanation": "具备可核验的官方来源和完整风险提示要素。",
        "risk_level": "可信新闻",
        "admin_note": "第五章截图演示数据",
    },
    {
        "title": "第五章演示：网传喝柠檬水三天清除血管垃圾",
        "content": (
            "网络文章称连续饮用柠檬水三天即可清除血管垃圾，但未提供医学研究、"
            "临床指南或监管机构来源。血脂、血压和动脉健康管理需要正规诊疗、"
            "饮食运动和医生指导，单一食物不能替代治疗。"
        ),
        "category": "健康",
        "truth_label": "疑似谣言",
        "source_name": "健康谣言核查样例",
        "source_url": "https://example.com/chapter5/lemon-water",
        "publish_time": datetime(2026, 6, 18, 14, 0),
        "summary": "单一食物不能替代慢病管理或医学治疗。",
        "keywords": "第五章演示,柠檬水,血管垃圾,健康谣言",
        "debunking_explanation": "存在夸大健康功效和缺乏可靠医学证据的问题。",
        "risk_level": "疑似谣言",
        "admin_note": "第五章截图演示数据",
    },
    {
        "title": "第五章演示：冒充学校收取紧急资料费",
        "content": (
            "家长群中出现自称班主任的账号，要求家长限时扫码缴纳资料费，"
            "但未通过学校官方通知渠道发布，也没有收费依据和票据说明。"
            "此类信息需要通过学校电话或班级官方渠道核实。"
        ),
        "category": "反诈",
        "truth_label": "高风险谣言",
        "source_name": "公安机关反诈提示",
        "source_url": "https://example.com/chapter5/school-fee-scam",
        "publish_time": datetime(2026, 6, 17, 10, 0),
        "summary": "冒充教师收取费用属于常见家长群诈骗场景。",
        "keywords": "第五章演示,家长群,扫码缴费,反诈",
        "debunking_explanation": "存在身份未核验、限时付款和个人收款码等风险。",
        "risk_level": "高风险谣言",
        "admin_note": "第五章截图演示数据",
    },
    {
        "title": "第五章演示：银行存款利率统一上调群消息",
        "content": (
            "聊天群消息称某银行今晚统一上调存款利率，并附个人客户经理二维码。"
            "银行利率和理财产品信息应以官网、手机银行和网点公告为准，"
            "个人二维码不能作为正式依据。"
        ),
        "category": "财经",
        "truth_label": "存疑信息",
        "source_name": "金融风险核查样例",
        "source_url": "https://example.com/chapter5/bank-rate-rumor",
        "publish_time": datetime(2026, 6, 16, 18, 30),
        "summary": "金融产品信息不能只依赖聊天群和个人二维码。",
        "keywords": "第五章演示,银行利率,个人二维码,金融风险",
        "debunking_explanation": "缺少银行官方公告，可能诱导私下转账或购买。",
        "risk_level": "存疑信息",
        "admin_note": "第五章截图演示数据",
    },
]


def upsert_user(db, row: dict[str, str]) -> User:
    user = db.query(User).filter(User.username == row["username"]).first()
    password_hash = get_password_hash(DEMO_PASSWORD)
    if user is None:
        user = User(
            username=row["username"],
            email=row["email"],
            password_hash=password_hash,
            role=row["role"],
            status="active",
        )
    else:
        user.email = row["email"]
        user.password_hash = password_hash
        user.role = row["role"]
        user.status = "active"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def upsert_knowledge(db, row: dict) -> KnowledgeItem:
    existing = db.query(KnowledgeItem).filter(KnowledgeItem.title == row["title"]).first()
    payload = KnowledgeCreate(**row)
    if existing is None:
        return create_knowledge_item(db, payload)
    return update_knowledge_item(db, int(existing.id), payload)


def ensure_prompt(db, admin_id: int) -> PromptTemplate:
    template = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.type == NEWS_CREDIBILITY_PROMPT_TYPE)
        .order_by(PromptTemplate.is_default.desc(), PromptTemplate.id.asc())
        .first()
    )
    if template is not None:
        return template

    content = (
        "你是新闻可信度评估助手。请基于新闻内容和候选证据输出JSON。"
        "新闻标题：{title}\n新闻正文：{content}\n候选证据：{evidence_list}"
    )
    template = PromptTemplate(
        name="第五章演示默认Prompt",
        type=NEWS_CREDIBILITY_PROMPT_TYPE,
        content=content,
        is_default=True,
        status="enabled",
        created_by=admin_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def main() -> None:
    with SessionLocal() as db:
        users = [upsert_user(db, row) for row in USERS]
        admin = next(user for user in users if user.role == "admin")
        prompt = ensure_prompt(db, int(admin.id))
        items = [upsert_knowledge(db, row) for row in KNOWLEDGE_ROWS]
        print(f"demo_password={DEMO_PASSWORD}")
        print("users=" + ",".join(f"{u.username}:{u.role}" for u in users))
        print(f"prompt_id={prompt.id}")
        print("knowledge=" + ",".join(f"{i.id}:{i.vector_sync_status}" for i in items))


if __name__ == "__main__":
    main()
