from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.crud.report_crud import get_report_by_detection_id
from app.crud.user import create_user, get_user_by_username
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.detection_record import DetectionRecord
from app.models.knowledge_item import KnowledgeItem
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.schemas.detection import DetectionCreate, EvidenceMatchCreate
from app.schemas.knowledge import KnowledgeCreate
from app.schemas.prompt import PromptTemplateCreate
from app.schemas.user import UserAdminCreate
from app.services.chroma_service import ChromaServiceError, get_knowledge_collection
from app.services.knowledge_service import create_knowledge_item, vectorize_knowledge_item
from app.services.prompt_service import create_prompt_template, set_default_prompt_template
from app.services.prompt_template_validator import NEWS_CREDIBILITY_PROMPT_TYPE
from app.services.report_service import ReportServiceError, generate_detection_report
from app.utils.high_risk import should_mark_high_risk


if TYPE_CHECKING:
    from sqlalchemy.orm import Session


DEMO_PASSWORD = "123456"

DEMO_USERS = (
    {
        "username": "user_demo",
        "email": "user_demo@example.com",
        "role": "user",
        "status": "active",
    },
    {
        "username": "user_demo2",
        "email": "user_demo2@example.com",
        "role": "user",
        "status": "active",
    },
    {
        "username": "admin_demo",
        "email": "admin_demo@example.com",
        "role": "admin",
        "status": "active",
    },
)

DEMO_PROMPT_CONTENT = """
你是“智闻辨真”的新闻可信度评估助手。请基于输入新闻、知识库检索证据和常识风险线索进行结构化评估。

新闻标题：{title}
新闻正文：{content}
检索证据：{evidence_list}

请严格输出 JSON，字段必须包括 llm_score、risk_level、reason、risk_points、keywords、suggestion。
risk_level 只能从“可信新闻、存疑信息、疑似谣言、高风险谣言”中选择。
""".strip()


def _demo_knowledge_rows(now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "title": "国家气象中心发布台风预警和防御指南",
            "content": "国家气象中心发布台风预警时，会同步说明影响海域、陆地风雨范围、防御建议和滚动更新渠道。公众应关注官方预警、避免前往危险海岸和山区，并按属地应急部门指引做好避险准备。",
            "summary": "官方气象预警通常包含影响范围、时间窗口和防御建议。",
            "category": "社会民生",
            "source_name": "国家气象中心公开信息",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "台风,气象预警,防御指南,官方发布",
            "debunking_explanation": "具备明确官方来源和可核验发布渠道。",
        },
        {
            "title": "市疾控通报流感疫苗接种安排",
            "content": "疾控机构发布疫苗接种安排时，会说明接种对象、预约方式、接种门诊、禁忌提示和不良反应处置流程。个人应通过疾控中心、社区卫生服务中心等正规渠道预约。",
            "summary": "疫苗安排以疾控和社区卫生服务机构公告为准。",
            "category": "健康",
            "source_name": "疾控中心公开提示",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "流感疫苗,疾控,接种,预约",
            "debunking_explanation": "来源清晰且内容符合公共卫生发布规范。",
        },
        {
            "title": "教育部门公布高校毕业生就业服务月",
            "content": "教育部门常通过官方网站和高校就业平台公布就业服务活动，包括线上招聘、政策宣讲、就业指导和基层项目报名入口。活动信息应以学校就业网和教育部门网站为准。",
            "summary": "高校就业服务信息应通过教育部门和学校官方渠道核验。",
            "category": "教育",
            "source_name": "教育部门公开通知",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "高校毕业生,就业服务,招聘,教育部门",
            "debunking_explanation": "具备可查的官方入口和明确政策背景。",
        },
        {
            "title": "市场监管总局提示保健食品标签规范",
            "content": "保健食品不得宣称治疗疾病，不得以专家患者名义作功效证明。消费者购买时应核对批准文号、适宜人群、不适宜人群和警示语，警惕夸大宣传。",
            "summary": "保健食品宣传应遵守标签规范，不能替代药物治疗。",
            "category": "消费",
            "source_name": "市场监管部门消费提示",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "保健食品,标签规范,消费提示,市场监管",
            "debunking_explanation": "内容与监管部门长期发布口径一致。",
        },
        {
            "title": "中国铁路发布假期增开列车安排",
            "content": "铁路部门在节假日前会根据客流增开列车，并通过 12306 网站、App 和车站公告发布车次信息。旅客购票应以 12306 官方渠道为准，避免通过不明链接购票。",
            "summary": "假期列车调整以 12306 和车站公告为准。",
            "category": "交通",
            "source_name": "铁路部门公开公告",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "铁路,12306,增开列车,假期出行",
            "debunking_explanation": "有固定官方发布平台，便于核验。",
        },
        {
            "title": "国家医保局说明异地就医备案流程",
            "content": "异地就医备案通常可通过国家医保服务平台、地方医保小程序或经办窗口办理。备案前应确认参保地政策、就医地定点机构和结算范围。",
            "summary": "异地就医备案应以医保官方平台和经办机构说明为准。",
            "category": "健康",
            "source_name": "医保部门办事指南",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "医保,异地就医,备案,结算",
            "debunking_explanation": "符合医保经办流程，信息可通过官方平台验证。",
        },
        {
            "title": "科研团队发布农业抗旱灌溉试验进展",
            "content": "农业科研试验通常会说明试验地点、作物品种、节水指标和适用条件。相关进展不等于立即大规模推广，应用前仍需结合当地水源、土壤和农技部门建议。",
            "summary": "科研进展需要区分试验结论和实际推广条件。",
            "category": "科技",
            "source_name": "科研机构新闻稿",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "农业科技,抗旱,灌溉,科研试验",
            "debunking_explanation": "表述审慎，未夸大试验效果。",
        },
        {
            "title": "公安机关提醒防范冒充客服退款诈骗",
            "content": "冒充电商客服、快递客服或支付平台客服要求转账、共享屏幕、提供验证码，是常见电信网络诈骗手法。遇到退款理赔应回到官方 App 或客服电话核验。",
            "summary": "退款理赔诈骗常以验证码、屏幕共享和转账为核心风险点。",
            "category": "反诈",
            "source_name": "公安机关反诈提示",
            "truth_label": "可信新闻",
            "risk_level": "可信新闻",
            "keywords": "反诈,退款,客服,验证码",
            "debunking_explanation": "与公安反诈宣传重点一致，具备明确防范建议。",
        },
        {
            "title": "网传某地将全面取消中考截图",
            "content": "微信群传播截图称某地将全面取消中考，但截图未显示发文机关、文号、发布日期和官方链接。教育政策调整通常需由教育部门正式发布，并配套过渡安排。",
            "summary": "缺少政策发布要素的截图需要进一步核验。",
            "category": "教育",
            "source_name": "课程演示核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "中考,政策截图,教育改革,网传",
            "debunking_explanation": "截图缺少官方来源和完整上下文，不能直接采信。",
        },
        {
            "title": "喝柠檬水三天清除血管垃圾说法",
            "content": "文章声称连续饮用柠檬水三天即可清除血管垃圾，但未提供医学研究来源。血脂、血压和动脉健康管理需要正规诊疗、饮食运动和医生指导。",
            "summary": "单一食物不能替代慢病管理和医疗建议。",
            "category": "健康",
            "source_name": "健康谣言核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "柠檬水,血管垃圾,慢病管理,健康养生",
            "debunking_explanation": "存在夸大健康功效，缺少可靠医学证据。",
        },
        {
            "title": "小区燃气检查必须现场缴费通知",
            "content": "楼道通知称燃气安全检查需现场缴纳服务费，未盖燃气公司或物业公章，也未提供客服电话。燃气安检一般会提前公告，收费项目应有正规票据和官方渠道。",
            "summary": "现场收费类通知需核实发布主体和收费依据。",
            "category": "社会民生",
            "source_name": "社区治理演示样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "燃气检查,现场缴费,小区通知,物业",
            "debunking_explanation": "收费主体不明确，存在冒充服务人员风险。",
        },
        {
            "title": "某银行存款利率今晚统一上调群消息",
            "content": "聊天群消息称某银行今晚统一上调存款利率并附理财经理二维码。银行利率和产品信息应以官网、手机银行和网点公告为准，个人二维码不能作为正式依据。",
            "summary": "金融产品信息不能只依据聊天群和个人二维码。",
            "category": "财经",
            "source_name": "金融风险核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "银行利率,理财经理,二维码,聊天群",
            "debunking_explanation": "缺少银行官方公告，可能诱导私下转账或购买。",
        },
        {
            "title": "地铁安检发现不明辐射物短视频",
            "content": "短视频称地铁安检发现不明辐射物，但画面无法识别城市、时间和处置单位。公共安全事件通常会由地铁运营方、公安或应急部门通报。",
            "summary": "公共安全短视频需核验地点、时间和官方处置通报。",
            "category": "公共安全",
            "source_name": "短视频核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "地铁安检,辐射物,短视频,公共安全",
            "debunking_explanation": "画面缺少关键背景，无法支撑确定性结论。",
        },
        {
            "title": "高校扩招名单内部流出表格",
            "content": "网传表格声称掌握高校扩招内部名单，但无教育部门文件编号和学校招生章程链接。招生计划调整应以教育考试院、学校招生网公告为准。",
            "summary": "招生信息必须通过教育考试机构和高校官网核验。",
            "category": "教育",
            "source_name": "招生信息核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "高校扩招,招生计划,内部名单,考试院",
            "debunking_explanation": "“内部名单”说法常见于招生诈骗，需谨慎。",
        },
        {
            "title": "新能源车充电桩月底全部免费海报",
            "content": "海报称本市所有新能源充电桩月底免费，但未标明主管部门、运营企业和活动细则。充电优惠通常由具体运营商发布，适用范围和时段有限。",
            "summary": "大范围免费活动应有主管部门或运营企业明确公告。",
            "category": "交通",
            "source_name": "城市服务核查样例",
            "truth_label": "存疑信息",
            "risk_level": "存疑信息",
            "keywords": "新能源车,充电桩,免费活动,海报",
            "debunking_explanation": "信息范围过大且缺少发布主体，可信度不足。",
        },
        {
            "title": "某品牌矿泉水含致癌物剪辑视频",
            "content": "视频剪辑称某品牌矿泉水含致癌物，但没有检测机构名称、批次、检测方法和原始报告。食品安全问题应以市场监管部门抽检结果和企业召回公告为依据。",
            "summary": "食品安全指控需有检测报告、批次和监管结论。",
            "category": "消费",
            "source_name": "食品安全核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "矿泉水,致癌物,剪辑视频,食品安全",
            "debunking_explanation": "缺少检测依据，视频剪辑易造成误导。",
        },
        {
            "title": "身份证照片可直接解锁所有支付软件传言",
            "content": "传言称只要获得身份证照片就能直接解锁所有支付软件。真实支付验证通常涉及设备、密码、人脸、短信或风控校验，但身份证照片泄露仍可能引发冒用风险。",
            "summary": "身份证照片泄露有风险，但“直接解锁所有支付软件”说法夸大。",
            "category": "反诈",
            "source_name": "网络安全核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "身份证,支付软件,信息泄露,风控",
            "debunking_explanation": "夸大单一材料的作用，容易制造恐慌。",
        },
        {
            "title": "吃特定水果可替代降压药文章",
            "content": "文章宣称吃某种水果可以替代降压药。高血压治疗需要医生评估和规范用药，擅自停药可能导致严重健康风险。水果只能作为均衡饮食的一部分。",
            "summary": "食疗不能替代医生开具的降压药。",
            "category": "健康",
            "source_name": "医学健康核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "降压药,水果,食疗,高血压",
            "debunking_explanation": "存在诱导停药风险，缺少临床依据。",
        },
        {
            "title": "高速服务区扫码领补贴链接",
            "content": "链接声称高速服务区扫码即可领取交通补贴，并要求填写身份证、银行卡和短信验证码。政府补贴不会通过来历不明二维码收集敏感信息。",
            "summary": "补贴领取链接索要银行卡和验证码时风险较高。",
            "category": "反诈",
            "source_name": "网络诈骗核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "高速服务区,扫码,补贴,验证码",
            "debunking_explanation": "具备钓鱼链接特征，需通过官方渠道核验。",
        },
        {
            "title": "某市将连续停水一周聊天记录",
            "content": "聊天记录称某市将连续停水一周，但供水公司和政府网站未发布公告。大范围停水通常会提前说明影响区域、时间、原因和应急供水安排。",
            "summary": "停水停电等民生信息应以主管部门和运营企业公告为准。",
            "category": "社会民生",
            "source_name": "城市运行核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "停水,聊天记录,供水公司,民生",
            "debunking_explanation": "缺少官方公告，传播链条不可追溯。",
        },
        {
            "title": "快递外包装统一携带病毒说法",
            "content": "说法称所有快递外包装都携带病毒，要求拒收快递。公共卫生风险应根据疾控部门通报和科学证据判断，日常可做好手卫生和外包装清洁。",
            "summary": "“所有快递都携带病毒”属于绝对化恐慌表述。",
            "category": "健康",
            "source_name": "公共卫生核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "快递,病毒,外包装,公共卫生",
            "debunking_explanation": "绝对化描述缺少证据，容易制造恐慌。",
        },
        {
            "title": "AI软件可保证高考押题命中广告",
            "content": "广告称 AI 软件可以保证高考押题命中，并要求支付高额会员费。正规教育服务不能保证命题命中，考生应警惕利用焦虑进行虚假宣传。",
            "summary": "“保证押题命中”属于高风险教育营销话术。",
            "category": "教育",
            "source_name": "教育培训核查样例",
            "truth_label": "疑似谣言",
            "risk_level": "疑似谣言",
            "keywords": "AI押题,高考,会员费,教育营销",
            "debunking_explanation": "承诺确定性结果且诱导付费，可信度低。",
        },
        {
            "title": "投资数字粮票每日返利20%骗局",
            "content": "所谓数字粮票投资承诺每日返利 20%，要求拉人头、充值 USDT 或银行卡转账。高收益、低风险、拉人返佣通常是非法集资或传销式骗局的重要特征。",
            "summary": "每日高额返利和拉人返佣是典型投资骗局信号。",
            "category": "财经",
            "source_name": "金融反诈演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "数字粮票,每日返利,非法集资,拉人头",
            "debunking_explanation": "高收益承诺明显异常，且要求私下转账和发展下线。",
        },
        {
            "title": "冒充疾控发放防疫补贴钓鱼链接",
            "content": "短信冒充疾控部门发放防疫补贴，点击后要求填写姓名、身份证、银行卡、密码和验证码。正规补贴不会索要银行卡密码和短信验证码。",
            "summary": "冒充公共部门发放补贴并索要验证码，属于钓鱼风险。",
            "category": "反诈",
            "source_name": "公安反诈演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "疾控,补贴,钓鱼链接,验证码",
            "debunking_explanation": "索要银行卡密码和验证码，具备明显诈骗特征。",
        },
        {
            "title": "虚假众筹称儿童急需手术",
            "content": "网帖使用旧照片称儿童急需手术，要求向个人账户转账。公益众筹应核验平台资质、医院证明、收款主体和项目更新，个人账户转账风险很高。",
            "summary": "公益求助需核验身份、医疗证明和收款主体。",
            "category": "公益",
            "source_name": "公益风险演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "虚假众筹,儿童手术,个人账户,旧照片",
            "debunking_explanation": "使用无法核验的旧照片并要求个人收款，风险高。",
        },
        {
            "title": "伪造官方文件要求企业转账验资",
            "content": "邮件伪造监管部门文件，要求企业限时向指定账户转账验资，否则吊销资质。行政机关不会通过个人账户收取验资款，正式通知应可在政务平台核验。",
            "summary": "伪造文件和限时转账是企业财务诈骗常见手法。",
            "category": "财经",
            "source_name": "企业反诈演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "伪造文件,企业转账,验资,监管部门",
            "debunking_explanation": "威胁式限时转账且收款账户异常，风险极高。",
        },
        {
            "title": "谣称银行即将倒闭引导挤兑",
            "content": "社交平台匿名账号称某银行即将倒闭，煽动储户立即排队取款，同时推荐所谓资金转移渠道。金融机构风险信息应以监管部门和银行官方公告为准。",
            "summary": "匿名金融恐慌消息可能引发社会风险，应谨慎传播。",
            "category": "财经",
            "source_name": "金融稳定演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "银行倒闭,挤兑,匿名账号,金融恐慌",
            "debunking_explanation": "匿名消息缺少依据，可能诱导恐慌和资金诈骗。",
        },
        {
            "title": "伪基站短信通知医保卡停用",
            "content": "短信称医保卡即将停用，点击链接可恢复使用。页面要求输入银行卡号、密码和验证码。医保业务应通过国家医保服务平台或当地医保局渠道办理。",
            "summary": "医保卡停用短信链接索要支付信息，属于高风险钓鱼。",
            "category": "健康",
            "source_name": "医保反诈演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "医保卡,伪基站,停用,银行卡",
            "debunking_explanation": "冒充医保业务并索要金融敏感信息，风险明确。",
        },
        {
            "title": "冒充学校收取紧急资料费",
            "content": "聊天群内有人冒充班主任，以紧急资料费名义要求家长扫码付款。学校收费应通过正式通知和指定平台，家长应电话核实老师身份。",
            "summary": "冒充老师收费是针对家长群的典型诈骗。",
            "category": "教育",
            "source_name": "校园反诈演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "家长群,班主任,资料费,扫码付款",
            "debunking_explanation": "身份无法核验且要求即时付款，具备诈骗特征。",
        },
        {
            "title": "虚假灾情视频诱导捐款",
            "content": "短视频使用外地旧灾情画面，配文称本地灾情严重并附个人收款码。灾情和捐赠信息应以应急管理、民政部门和正规公益平台为准。",
            "summary": "旧视频冒充本地灾情并附个人收款码，风险很高。",
            "category": "公益",
            "source_name": "应急公益演示样例",
            "truth_label": "高风险谣言",
            "risk_level": "高风险谣言",
            "keywords": "灾情视频,个人收款码,旧画面,公益捐款",
            "debunking_explanation": "视频来源和收款主体不可信，可能骗取善款。",
        },
    ]

    for index, row in enumerate(rows):
        item_time = now - timedelta(days=45 - index)
        row["source_url"] = f"https://example.com/demo/knowledge/{index + 1}"
        row["publish_time"] = item_time
        row["created_at"] = item_time
        row["updated_at"] = item_time
        row["admin_note"] = "第七阶段课程答辩演示知识库数据"
    return rows


def _demo_detection_rows(now: datetime) -> list[dict[str, Any]]:
    base_rows: list[dict[str, Any]] = [
        {
            "user": "user_demo",
            "input_title": "国家气象中心发布台风蓝色预警，请沿海居民注意防范",
            "input_content": "新闻称国家气象中心发布台风蓝色预警，提示沿海地区关注大风和强降雨，并建议公众通过官方渠道获取滚动预警。",
            "category": "社会民生",
            "keywords": ["台风", "气象预警", "官方发布"],
            "final_score": 91,
            "evidence_score": 92,
            "llm_score": 90,
            "rule_score": 91,
            "risk_level": "可信新闻",
            "judgement_result": "信息可信，具备明确官方来源",
            "reason": "标题、正文和知识库中的官方气象预警信息一致，未发现夸大或诱导性表述。",
            "risk_points": ["需关注预警是否为最新版本"],
            "suggestion": "截图答辩时可展示评分、证据和建议字段。",
            "evidence_title": "国家气象中心发布台风预警和防御指南",
            "days_ago": 0,
        },
        {
            "user": "user_demo2",
            "input_title": "社区卫生中心公布流感疫苗接种预约时间",
            "input_content": "消息说明预约方式、接种门诊和注意事项，并提醒居民以社区卫生服务中心公告为准。",
            "category": "健康",
            "keywords": ["流感疫苗", "疾控", "社区卫生"],
            "final_score": 88,
            "evidence_score": 90,
            "llm_score": 87,
            "rule_score": 88,
            "risk_level": "可信新闻",
            "judgement_result": "信息基本可信",
            "reason": "内容与疾控疫苗接种安排知识库记录匹配，未索要异常个人信息。",
            "risk_points": ["仍需核验本地接种门诊排班"],
            "suggestion": "建议通过疾控中心或社区卫生服务中心官方入口预约。",
            "evidence_title": "市疾控通报流感疫苗接种安排",
            "days_ago": 1,
        },
        {
            "user": "user_demo",
            "input_title": "铁路部门端午前增开多趟热门方向列车",
            "input_content": "报道引用铁路部门公告，提醒旅客通过 12306 查询车次余票并避免第三方不明链接购票。",
            "category": "交通",
            "keywords": ["铁路", "12306", "假期出行"],
            "final_score": 89,
            "evidence_score": 91,
            "llm_score": 88,
            "rule_score": 89,
            "risk_level": "可信新闻",
            "judgement_result": "信息可信",
            "reason": "与铁路官方假期增开列车安排类知识匹配，具有明确核验渠道。",
            "risk_points": ["具体车次以 12306 实时查询为准"],
            "suggestion": "通过 12306 官方平台查询和购票。",
            "evidence_title": "中国铁路发布假期增开列车安排",
            "days_ago": 2,
        },
        {
            "user": "user_demo2",
            "input_title": "医保异地备案可在国家医保服务平台办理",
            "input_content": "消息介绍国家医保服务平台备案入口，并说明备案前要确认参保地政策和定点医院范围。",
            "category": "健康",
            "keywords": ["医保", "异地就医", "备案"],
            "final_score": 92,
            "evidence_score": 93,
            "llm_score": 91,
            "rule_score": 92,
            "risk_level": "可信新闻",
            "judgement_result": "信息可信",
            "reason": "内容与医保部门公开办事流程一致，没有诱导转账和索要验证码。",
            "risk_points": ["不同地区备案规则可能存在差异"],
            "suggestion": "以国家医保服务平台和参保地医保局说明为准。",
            "evidence_title": "国家医保局说明异地就医备案流程",
            "days_ago": 3,
        },
        {
            "user": "user_demo",
            "input_title": "公安提醒警惕冒充客服退款骗局",
            "input_content": "报道提醒用户遇到退款理赔时不要共享屏幕，不要提供验证码，应回到官方 App 核验订单。",
            "category": "反诈",
            "keywords": ["反诈", "客服退款", "验证码"],
            "final_score": 90,
            "evidence_score": 92,
            "llm_score": 88,
            "rule_score": 90,
            "risk_level": "可信新闻",
            "judgement_result": "信息可信",
            "reason": "与公安机关反诈提示高度一致，可作为用户端可信新闻示例。",
            "risk_points": ["不同平台退款流程可能不同"],
            "suggestion": "遇到退款问题应回到官方 App 或客服电话核验。",
            "evidence_title": "公安机关提醒防范冒充客服退款诈骗",
            "days_ago": 4,
        },
        {
            "user": "user_demo2",
            "input_title": "网传本市将全面取消中考，教育部门尚未发布通知",
            "input_content": "多个微信群转发截图称本市将全面取消中考，但截图没有发文机关和文号，目前教育部门官网未见相关公告。",
            "category": "教育",
            "keywords": ["中考", "政策截图", "教育改革"],
            "final_score": 66,
            "evidence_score": 62,
            "llm_score": 68,
            "rule_score": 67,
            "risk_level": "存疑信息",
            "judgement_result": "信息存疑，需要官方核验",
            "reason": "该信息与知识库中的存疑截图样例相似，缺少政策发布基本要素。",
            "risk_points": ["缺少官方来源", "截图容易被裁剪或伪造"],
            "suggestion": "等待教育部门或学校正式通知，不建议继续扩散截图。",
            "evidence_title": "网传某地将全面取消中考截图",
            "days_ago": 5,
        },
        {
            "user": "user_demo",
            "input_title": "喝柠檬水三天清除血管垃圾的养生帖",
            "input_content": "文章声称每天喝柠檬水三天即可清理血管垃圾，不需要体检和药物管理。",
            "category": "健康",
            "keywords": ["柠檬水", "血管垃圾", "养生"],
            "final_score": 58,
            "evidence_score": 55,
            "llm_score": 60,
            "rule_score": 59,
            "risk_level": "存疑信息",
            "judgement_result": "健康功效明显夸大",
            "reason": "知识库提示单一食物不能替代慢病管理，原文缺少医学证据。",
            "risk_points": ["夸大食疗效果", "可能误导慢病患者"],
            "suggestion": "涉及疾病治疗时应咨询医生，不要擅自停药。",
            "evidence_title": "喝柠檬水三天清除血管垃圾说法",
            "days_ago": 6,
        },
        {
            "user": "user_demo2",
            "input_title": "楼道通知称燃气检查必须现场缴费",
            "input_content": "通知没有公司公章，要求居民当天现场缴纳服务费，否则停止供气。",
            "category": "社会民生",
            "keywords": ["燃气检查", "现场缴费", "物业"],
            "final_score": 62,
            "evidence_score": 60,
            "llm_score": 64,
            "rule_score": 62,
            "risk_level": "存疑信息",
            "judgement_result": "收费通知存疑",
            "reason": "知识库显示燃气安检收费应有正规依据，通知主体不明确。",
            "risk_points": ["收费主体不明", "存在冒充服务人员风险"],
            "suggestion": "联系燃气公司官方客服电话或物业核验。",
            "evidence_title": "小区燃气检查必须现场缴费通知",
            "days_ago": 0,
        },
        {
            "user": "user_demo",
            "input_title": "某银行利率今晚统一上调，群内二维码可提前预约",
            "input_content": "群消息称扫码添加理财经理即可锁定高利率存款名额，名额有限。",
            "category": "财经",
            "keywords": ["银行利率", "二维码", "理财经理"],
            "final_score": 61,
            "evidence_score": 58,
            "llm_score": 64,
            "rule_score": 61,
            "risk_level": "存疑信息",
            "judgement_result": "金融信息存疑",
            "reason": "银行利率应以官方渠道为准，个人二维码预约存在风险。",
            "risk_points": ["缺少银行公告", "诱导添加个人联系方式"],
            "suggestion": "通过银行官网、手机银行或网点核验产品信息。",
            "evidence_title": "某银行存款利率今晚统一上调群消息",
            "days_ago": 1,
        },
        {
            "user": "user_demo2",
            "input_title": "短视频称地铁安检发现不明辐射物",
            "input_content": "视频画面无法识别城市和时间，评论区大量转发但没有运营方通报。",
            "category": "公共安全",
            "keywords": ["地铁安检", "辐射物", "短视频"],
            "final_score": 63,
            "evidence_score": 60,
            "llm_score": 66,
            "rule_score": 63,
            "risk_level": "存疑信息",
            "judgement_result": "公共安全信息存疑",
            "reason": "缺少地点、时间和官方处置通报，与知识库短视频存疑样例相符。",
            "risk_points": ["画面上下文缺失", "容易引发恐慌"],
            "suggestion": "关注地铁运营方、公安或应急部门通报。",
            "evidence_title": "地铁安检发现不明辐射物短视频",
            "days_ago": 2,
        },
        {
            "user": "user_demo",
            "input_title": "网传某品牌矿泉水含致癌物但无检测报告",
            "input_content": "视频只展示剪辑画面，没有检测机构、批次、检测方法和监管部门结论。",
            "category": "消费",
            "keywords": ["矿泉水", "致癌物", "食品安全"],
            "final_score": 47,
            "evidence_score": 45,
            "llm_score": 49,
            "rule_score": 47,
            "risk_level": "疑似谣言",
            "judgement_result": "疑似谣言，缺少关键证据",
            "reason": "食品安全指控需有监管抽检或检测报告，原视频缺少基本核验要素。",
            "risk_points": ["缺少检测报告", "剪辑视频容易误导"],
            "suggestion": "以市场监管抽检公告和企业召回信息为准。",
            "evidence_title": "某品牌矿泉水含致癌物剪辑视频",
            "days_ago": 3,
        },
        {
            "user": "user_demo2",
            "input_title": "身份证照片可直接解锁所有支付软件的传言",
            "input_content": "文章称只要身份证照片泄露，所有支付软件都会被直接打开并转走资金。",
            "category": "反诈",
            "keywords": ["身份证", "支付软件", "信息泄露"],
            "final_score": 52,
            "evidence_score": 50,
            "llm_score": 54,
            "rule_score": 52,
            "risk_level": "疑似谣言",
            "judgement_result": "说法夸大但提醒有一定价值",
            "reason": "身份证泄露有风险，但“直接解锁所有支付软件”缺少事实依据。",
            "risk_points": ["夸大风险", "可能制造恐慌"],
            "suggestion": "保护身份信息，遇到账户异常应联系平台官方客服。",
            "evidence_title": "身份证照片可直接解锁所有支付软件传言",
            "days_ago": 4,
        },
        {
            "user": "user_demo",
            "input_title": "吃水果可以替代降压药的健康文章",
            "input_content": "文章建议高血压患者停止服药，改为每天大量食用某种水果。",
            "category": "健康",
            "keywords": ["降压药", "水果", "高血压"],
            "final_score": 44,
            "evidence_score": 42,
            "llm_score": 46,
            "rule_score": 44,
            "risk_level": "疑似谣言",
            "judgement_result": "疑似谣言且有健康风险",
            "reason": "知识库明确指出食疗不能替代降压药，擅自停药可能造成严重后果。",
            "risk_points": ["诱导停药", "缺少临床证据"],
            "suggestion": "不要擅自调整药物，需咨询医生。",
            "evidence_title": "吃特定水果可替代降压药文章",
            "days_ago": 5,
        },
        {
            "user": "user_demo2",
            "input_title": "高速服务区扫码领交通补贴链接",
            "input_content": "链接要求输入身份证、银行卡、支付密码和短信验证码后才能领取补贴。",
            "category": "反诈",
            "keywords": ["高速服务区", "扫码", "补贴", "验证码"],
            "final_score": 41,
            "evidence_score": 38,
            "llm_score": 44,
            "rule_score": 41,
            "risk_level": "疑似谣言",
            "judgement_result": "疑似诈骗链接",
            "reason": "补贴链接索要银行卡密码和验证码，符合钓鱼链接风险特征。",
            "risk_points": ["索要验证码", "收集金融敏感信息"],
            "suggestion": "不要填写信息，向交通或公安反诈渠道核验。",
            "evidence_title": "高速服务区扫码领补贴链接",
            "days_ago": 6,
        },
        {
            "user": "user_demo",
            "input_title": "AI软件保证高考押题命中，会员费三千元",
            "input_content": "广告称系统可保证高考押题命中，错过将无法获得内部资料。",
            "category": "教育",
            "keywords": ["AI押题", "高考", "会员费"],
            "final_score": 49,
            "evidence_score": 46,
            "llm_score": 51,
            "rule_score": 49,
            "risk_level": "疑似谣言",
            "judgement_result": "教育营销疑似谣言",
            "reason": "保证命中属于不合理承诺，且以焦虑营销诱导付费。",
            "risk_points": ["承诺确定性结果", "高额会员费"],
            "suggestion": "不要相信保过、必中等绝对化承诺。",
            "evidence_title": "AI软件可保证高考押题命中广告",
            "days_ago": 0,
        },
        {
            "user": "user_demo",
            "input_title": "投资数字粮票每日返利20%，邀请好友再返佣",
            "input_content": "平台宣称国家试点数字粮票投资，每日返利 20%，充值越多收益越高，还鼓励邀请好友获得返佣。",
            "category": "财经",
            "keywords": ["数字粮票", "每日返利", "非法集资", "拉人头"],
            "final_score": 22,
            "evidence_score": 18,
            "llm_score": 25,
            "rule_score": 23,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险投资诈骗",
            "reason": "每日高额返利、拉人返佣和私下充值均符合非法集资或传销式骗局特征。",
            "risk_points": ["高额返利", "拉人头", "私下转账"],
            "suggestion": "不要充值和转发，保留证据并向反诈平台举报。",
            "evidence_title": "投资数字粮票每日返利20%骗局",
            "days_ago": 0,
            "review_status": "approved",
            "is_public": True,
            "admin_remark": "答辩演示：已审核且公开的高风险投资骗局。",
        },
        {
            "user": "user_demo2",
            "input_title": "医保卡即将停用，短信链接要求输入银行卡和验证码",
            "input_content": "短信自称医保中心，称医保卡即将停用，用户点击链接后需要输入银行卡号、密码和短信验证码。",
            "category": "健康",
            "keywords": ["医保卡", "伪基站", "银行卡", "验证码"],
            "final_score": 28,
            "evidence_score": 24,
            "llm_score": 30,
            "rule_score": 29,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险钓鱼诈骗",
            "reason": "医保业务不会索要银行卡密码和验证码，链接具备明显钓鱼特征。",
            "risk_points": ["冒充医保", "索要银行卡密码", "索要验证码"],
            "suggestion": "立即停止填写信息，通过国家医保服务平台或医保局核验。",
            "evidence_title": "伪基站短信通知医保卡停用",
            "days_ago": 1,
            "review_status": "approved",
            "is_public": True,
            "admin_remark": "答辩演示：已审核且公开的高风险医保钓鱼短信。",
        },
        {
            "user": "user_demo",
            "input_title": "家长群内班主任要求扫码缴纳紧急资料费",
            "input_content": "群内头像和昵称疑似班主任，通知所有家长立即扫码缴纳资料费，否则学生无法领取复习资料。",
            "category": "教育",
            "keywords": ["家长群", "班主任", "资料费", "扫码付款"],
            "final_score": 32,
            "evidence_score": 30,
            "llm_score": 34,
            "rule_score": 32,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险校园收费诈骗",
            "reason": "冒充老师收费、限时扫码付款是家长群诈骗典型手法。",
            "risk_points": ["身份未核验", "限时付款", "扫码收款"],
            "suggestion": "电话联系老师或学校核实，不要在群内直接付款。",
            "evidence_title": "冒充学校收取紧急资料费",
            "days_ago": 2,
            "review_status": "approved",
            "is_public": False,
            "admin_remark": "答辩演示：已审核但暂不公开。",
        },
        {
            "user": "user_demo2",
            "input_title": "旧灾情视频配本地定位并附个人收款码",
            "input_content": "短视频使用旧灾情画面，配文称本地突发严重灾情，要求网友向个人收款码捐款。",
            "category": "公益",
            "keywords": ["灾情视频", "个人收款码", "公益捐款"],
            "final_score": 26,
            "evidence_score": 23,
            "llm_score": 28,
            "rule_score": 26,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险虚假公益募捐",
            "reason": "旧视频冒充本地灾情且附个人收款码，存在骗取善款风险。",
            "risk_points": ["旧画面冒充新灾情", "个人收款码", "缺少正规公益主体"],
            "suggestion": "通过民政部门和正规公益平台核验捐赠项目。",
            "evidence_title": "虚假灾情视频诱导捐款",
            "days_ago": 3,
            "review_status": "pending",
            "is_public": False,
            "admin_remark": "答辩演示：待管理员审核。",
        },
        {
            "user": "user_demo",
            "input_title": "匿名账号称某银行即将倒闭，催促储户立即取款",
            "input_content": "匿名账号声称某银行即将倒闭，并推荐所谓安全转移账户，引导用户恐慌取款。",
            "category": "财经",
            "keywords": ["银行倒闭", "挤兑", "金融恐慌"],
            "final_score": 34,
            "evidence_score": 31,
            "llm_score": 36,
            "rule_score": 34,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险金融谣言",
            "reason": "匿名金融恐慌信息可能诱导挤兑和资金诈骗，缺少监管或银行公告。",
            "risk_points": ["匿名消息", "煽动恐慌", "推荐转移资金"],
            "suggestion": "以监管部门和银行官方公告为准，不要跟随匿名账号转账。",
            "evidence_title": "谣称银行即将倒闭引导挤兑",
            "days_ago": 4,
            "review_status": "rejected",
            "is_public": False,
            "admin_remark": "答辩演示：已驳回，不能公开。",
        },
        {
            "user": "user_demo2",
            "input_title": "疾控补贴短信要求填写银行卡密码",
            "input_content": "短信自称疾控部门发放补贴，点击链接后要求填写银行卡、密码和验证码。",
            "category": "反诈",
            "keywords": ["疾控", "补贴", "钓鱼链接", "验证码"],
            "final_score": 24,
            "evidence_score": 20,
            "llm_score": 26,
            "rule_score": 25,
            "risk_level": "高风险谣言",
            "judgement_result": "高风险钓鱼诈骗",
            "reason": "公共部门不会通过短信链接索要银行卡密码和验证码。",
            "risk_points": ["冒充疾控", "钓鱼链接", "索要验证码"],
            "suggestion": "删除短信，通过官方渠道核验，不要输入任何支付信息。",
            "evidence_title": "冒充疾控发放防疫补贴钓鱼链接",
            "days_ago": 5,
            "review_status": "approved",
            "is_public": True,
            "admin_remark": "答辩演示：已审核且公开的高风险钓鱼链接。",
        },
    ]

    for index, row in enumerate(base_rows):
        row["created_at"] = now - timedelta(days=row["days_ago"], hours=index % 5)
    return base_rows


def ensure_schema_ready() -> None:
    Base.metadata.create_all(bind=engine)

    required_columns = {
        "users": {"username", "password_hash", "role", "status"},
        "knowledge_items": {
            "title",
            "content",
            "category",
            "truth_label",
            "source_name",
            "summary",
            "keywords",
            "risk_level",
            "vector_sync_status",
        },
        "detection_records": {
            "user_id",
            "input_title",
            "input_content",
            "category",
            "keywords",
            "final_score",
            "evidence_score",
            "llm_score",
            "rule_score",
            "risk_level",
            "judgement_result",
            "reason",
            "risk_points",
            "suggestion",
            "is_high_risk",
            "review_status",
            "is_public",
            "reviewed_at",
            "reviewed_by",
        },
        "evidence_matches": {
            "detection_id",
            "knowledge_id",
            "title",
            "summary",
            "source_name",
            "similarity_score",
            "rank_order",
        },
        "reports": {"detection_id", "pdf_path"},
        "prompt_templates": {"name", "type", "content", "is_default", "status"},
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table_name, columns in required_columns.items():
        if table_name not in existing_tables:
            raise RuntimeError(f"数据库表缺失：{table_name}。请先执行 python -m app.db.init_db。")
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing_columns = sorted(columns - existing_columns)
        if missing_columns:
            hint = ""
            if table_name == "detection_records":
                hint = (
                    " 现有库可能缺少高风险审核字段，请执行 "
                    "backend/migrations/20260604_add_high_risk_review_fields.sql。"
                )
            raise RuntimeError(
                f"数据库表 {table_name} 缺少字段：{', '.join(missing_columns)}。{hint}"
            )


def ensure_output_dirs() -> None:
    settings = get_settings()
    Path(settings.chroma_persist_path).mkdir(parents=True, exist_ok=True)
    Path(settings.report_path).mkdir(parents=True, exist_ok=True)


def ensure_demo_users(db: Session) -> dict[str, User]:
    users: dict[str, User] = {}
    for row in DEMO_USERS:
        user = get_user_by_username(db, row["username"])
        if user is None:
            user = db.query(User).filter(User.email == row["email"]).first()
        password_hash = get_password_hash(DEMO_PASSWORD)
        if user is None:
            payload = UserAdminCreate(
                username=row["username"],
                email=row["email"],
                password=DEMO_PASSWORD,
                role=row["role"],
                status=row["status"],
            )
            user = create_user(
                db,
                user_in=payload,
                password_hash=password_hash,
                role=row["role"],
                status=row["status"],
            )
        else:
            username_owner = (
                db.query(User)
                .filter(User.username == row["username"], User.id != user.id)
                .first()
            )
            if username_owner is None:
                user.username = row["username"]
            user.password_hash = password_hash
            user.role = row["role"]
            user.status = row["status"]
            email_owner = (
                db.query(User)
                .filter(User.email == row["email"], User.id != user.id)
                .first()
            )
            if email_owner is None:
                user.email = row["email"]
            db.add(user)
            db.commit()
            db.refresh(user)
        users[row["username"]] = user
    return users


def ensure_demo_prompt(db: Session, admin: User) -> PromptTemplate:
    template = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.name == "第七阶段新闻可信度默认Prompt")
        .first()
    )
    if template is None:
        template = create_prompt_template(
            db,
            PromptTemplateCreate(
                name="第七阶段新闻可信度默认Prompt",
                type=NEWS_CREDIBILITY_PROMPT_TYPE,
                content=DEMO_PROMPT_CONTENT,
                is_default=True,
                status="enabled",
            ),
            created_by=int(admin.id),
        )
    else:
        template.content = DEMO_PROMPT_CONTENT
        template.status = "enabled"
        db.add(template)
        db.commit()
        db.refresh(template)
        if not template.is_default:
            template = set_default_prompt_template(db, int(template.id))
    return template


def ensure_knowledge_items(db: Session, now: datetime) -> dict[str, KnowledgeItem]:
    items: dict[str, KnowledgeItem] = {}
    for row in _demo_knowledge_rows(now):
        timestamp = row["created_at"]
        payload_data = {
            key: value
            for key, value in row.items()
            if key not in {"created_at", "updated_at"}
        }
        item = db.query(KnowledgeItem).filter(KnowledgeItem.title == row["title"]).first()
        if item is None:
            item = create_knowledge_item(db, KnowledgeCreate(**payload_data))
        else:
            for field, value in payload_data.items():
                setattr(item, field, value)
            item.vector_sync_status = "pending"
            item.vector_sync_error = None
            db.add(item)
            db.commit()
            db.refresh(item)
            item = vectorize_knowledge_item(db, int(item.id))

        item.created_at = timestamp
        item.updated_at = row["updated_at"]
        db.add(item)
        db.commit()
        db.refresh(item)
        items[item.title] = item
    return items


def _build_evidence(
    knowledge_items: dict[str, KnowledgeItem],
    evidence_title: str,
) -> list[EvidenceMatchCreate]:
    item = knowledge_items[evidence_title]
    return [
        EvidenceMatchCreate(
            knowledge_id=int(item.id),
            title=item.title,
            summary=item.summary,
            source_name=item.source_name,
            similarity_score=0.86,
            rank_order=1,
        )
    ]


def _apply_detection_state(
    db: Session,
    record: DetectionRecord,
    row: dict[str, Any],
    admin: User,
) -> DetectionRecord:
    created_at = row["created_at"]
    review_status = row.get("review_status", "pending")
    is_public = bool(row.get("is_public", False))

    record.created_at = created_at
    record.review_status = review_status
    record.is_public = is_public if review_status == "approved" else False
    record.admin_remark = row.get("admin_remark")
    record.is_high_risk = should_mark_high_risk(row["final_score"], row["risk_level"])
    if review_status == "pending":
        record.reviewed_at = None
        record.reviewed_by = None
    else:
        record.reviewed_at = created_at + timedelta(hours=2)
        record.reviewed_by = int(admin.id)

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def ensure_detection_records(
    db: Session,
    users: dict[str, User],
    knowledge_items: dict[str, KnowledgeItem],
    admin: User,
    now: datetime,
) -> list[DetectionRecord]:
    records: list[DetectionRecord] = []
    for row in _demo_detection_rows(now):
        owner = users[row["user"]]
        keywords = ",".join(row["keywords"])
        record = (
            db.query(DetectionRecord)
            .filter(
                DetectionRecord.input_title == row["input_title"],
                DetectionRecord.user_id == int(owner.id),
            )
            .first()
        )

        if record is None:
            payload = DetectionCreate(
                user_id=int(owner.id),
                input_title=row["input_title"],
                input_content=row["input_content"],
                category=row["category"],
                keywords=keywords,
                final_score=row["final_score"],
                evidence_score=row["evidence_score"],
                llm_score=row["llm_score"],
                rule_score=row["rule_score"],
                risk_level=row["risk_level"],
                judgement_result=row["judgement_result"],
                reason=row["reason"],
                risk_points=row["risk_points"],
                suggestion=row["suggestion"],
                evidence_matches=_build_evidence(knowledge_items, row["evidence_title"]),
            )
            from app.crud.detection_crud import save_detection_record

            record = save_detection_record(db, payload)
        else:
            record.input_content = row["input_content"]
            record.category = row["category"]
            record.keywords = keywords
            record.final_score = row["final_score"]
            record.evidence_score = row["evidence_score"]
            record.llm_score = row["llm_score"]
            record.rule_score = row["rule_score"]
            record.risk_level = row["risk_level"]
            record.judgement_result = row["judgement_result"]
            record.reason = row["reason"]
            record.risk_points = json.dumps(row["risk_points"], ensure_ascii=False)
            record.suggestion = row["suggestion"]

        record = _apply_detection_state(db, record, row, admin)
        records.append(record)
    return records


def ensure_demo_report(db: Session, records: list[DetectionRecord]) -> str:
    for record in records:
        if record.user_id is None:
            continue
        owner = db.query(User).filter(User.id == record.user_id).first()
        if owner is None or owner.username != "user_demo":
            continue
        existing_report = get_report_by_detection_id(db, int(record.id))
        if existing_report is not None and existing_report.pdf_path:
            return f"skipped existing report_id={existing_report.id}"
        try:
            report = generate_detection_report(db, int(record.id), owner)
        except ReportServiceError as exc:
            return f"warning: PDF 报告生成失败，检测记录仍可用于手动生成：{exc}"
        except Exception as exc:
            return f"warning: PDF 报告生成出现未知异常，检测记录仍可用于手动生成：{exc}"
        return f"generated report_id={report.id}"
    return "warning: 未找到 user_demo 的检测记录，未生成报告"


def chroma_count() -> int | None:
    try:
        return int(get_knowledge_collection().count())
    except ChromaServiceError:
        return None


def main() -> None:
    now = datetime.now().replace(microsecond=0)
    try:
        ensure_schema_ready()
        ensure_output_dirs()
        with SessionLocal() as db:
            users = ensure_demo_users(db)
            admin = users["admin_demo"]
            prompt = ensure_demo_prompt(db, admin)
            knowledge_items = ensure_knowledge_items(db, now)
            records = ensure_detection_records(db, users, knowledge_items, admin, now)
            report_status = ensure_demo_report(db, records)
            prompt_id = int(prompt.id)
            knowledge_count = len(knowledge_items)
            record_count = len(records)
            public_high_risk = (
                db.query(DetectionRecord)
                .filter(
                    DetectionRecord.is_high_risk.is_(True),
                    DetectionRecord.review_status == "approved",
                    DetectionRecord.is_public.is_(True),
                )
                .count()
            )
            synced_knowledge = (
                db.query(KnowledgeItem)
                .filter(KnowledgeItem.vector_sync_status == "synced")
                .count()
            )
            settings = get_settings()
            vector_count = chroma_count()

        print("[ok] 演示账号已初始化：user_demo / user_demo2 / admin_demo，密码均为 123456")
        print(f"[ok] Prompt 模板已初始化：id={prompt_id}")
        print(f"[ok] 知识库演示数据已初始化：{knowledge_count} 条，MySQL synced={synced_knowledge}")
        print(f"[ok] 检测记录演示数据已初始化：{record_count} 条")
        print(f"[ok] 用户端公开高风险记录：{public_high_risk} 条")
        if vector_count is None:
            print("[warn] Chroma collection count 获取失败，请检查 chromadb 依赖和 CHROMA_PATH。")
        else:
            print(f"[ok] Chroma collection count={vector_count}")
        print(f"[ok] PDF 报告状态：{report_status}")
        print(f"[ok] REPORT_DIR={settings.report_path}")
        print(f"[ok] CHROMA_PATH={settings.chroma_persist_path}")
    except SQLAlchemyError as exc:
        settings = get_settings()
        if not settings.env_file_exists:
            print(
                "[error] backend/.env 不存在。请复制 backend/.env.example 为 backend/.env，"
                "填写 MySQL 配置后再运行 seed。"
            )
        else:
            print(
                "[error] 演示数据初始化失败：数据库无法连接或写入。"
                "请检查 MySQL 服务、DATABASE_URL 或 DATABASE_* 配置和数据库是否已创建。"
            )
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"[error] {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
