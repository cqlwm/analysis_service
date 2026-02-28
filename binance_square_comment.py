import time
import dotenv
from playwright.sync_api import Page, TimeoutError
from typing import List, Dict

from attach_existing_chrome import ensure_debug_chrome_running, open_page
from llm import LLMManager
from logger import setup_logger

logger = setup_logger('square_comment')

dotenv.load_dotenv()

llm = LLMManager()

SQUARE_URL = "https://www.binance.com/zh-CN/square"


def get_posts_from_page(page: Page) -> List[Dict]:
    """从当前页面获取所有 posts"""
    posts = []
    
    time.sleep(2)
    
    card_boxes = page.locator('.card-content-box').all()
    logger.info(f"找到 {len(card_boxes)} 个 card-content-box")
    
    for i, card in enumerate(card_boxes):
        try:
            link = card.locator('div.feed-content-text>a')
            if link.count() == 0:
                continue
            link = link.first
            href = link.get_attribute('href')
            text = link.text_content()

            if href and text and len(text.strip()) > 0:
                posts.append({
                    'url': href or '',
                    'content': text.strip(),
                    'index': i,
                    'card': card
                })
                logger.debug(f"Post {i}: {text[:50]}...")
            else:
                raise
        except Exception as e:
            logger.warning(f"解析 post {i} 失败: {e}")
            continue
    
    logger.info(f"共获取 {len(posts)} 个 posts")
    return posts


def analyze_post_with_llm(post: Dict) -> str:
    """使用 LLM 分析 post 并生成评论"""
    content = post['content']
    if not content or len(content) < 5:
        return "👍"
    
    prompt = f"""你是一位犀利、一针见血、冷静客观的加密货币社区评论员，资深交易员，风格简短有力、有深度、带哲学感。
请对下面帖文给出一句评论：
{content}

要求：
- 只写一句话
- 20 字以内最佳
- 风格犀利、扎心、适合币圈热评
- 不煽情、不啰嗦、不解释
- 直接输出评论内容，不要添加任何前缀或解释

评论示例:

广场帖文:
住手，你们不要再打了！
币圈韭菜已经凑不齐你们的军费💰开支了
😭😭😭😭😭
$ETH

你的回复:
天天互撕、拉盘砸盘、画饼收割，最后只会把整个池子抽干
-------
广场帖文:
跟着cz囤币的第58天，继续定投ASTER，数量已经来到了恐怖的3000枚😂

你的回复:
定投策略不仅适用于买入，也适用于卖出
-------
如果你实在不知道该怎么评论，可以参考下面的内容，给出一些万能回复：
大多数人在加密货币领域亏损并非因为愚蠢
而是因为他们从不锁定盈利
如果你的币已经上涨了三倍，而且没有新的催化剂——那就开始卖出吧
你不需要守住最高点——你需要的是及时退出
定投策略不仅适用于买入，也适用于卖出
在成交量激增、推特上热闹非凡时分批退出
不要在人人恐慌时退出，而要在众人狂热时退出
贪婪比任何熊市都更能摧毁投资组合
别对你的投资标的抱有执念——及时抛售
只有真正理解其基本面，才考虑长期持有
95% 的山寨币注定要被抛售，而不是被真正看好
市场风向会变——你的投资标的也应该随之改变
叙事能印钞票——学会如何找到它们
在热门趋势出现之前，先看看哪些精明的投资者正在耕耘
新的链条、新的基础、新的激励机制 = 新的利润
关注钱包，而非言论
聪明的资金不会追逐上涨的K线
它们会在代币死气沉沉、流动性差、无人问津时入场
学会享受沉默——价格上涨往往从那里开始
使用工具追踪钱包，而不是依赖信息流
关注流动性的流动——而不仅仅是图表
巨鲸是在增持还是减持？
开发者是在持续开发还是销声匿迹？
在图表确认之前，总会有一些迹象出现
避免与巨鲸公开交战
如果你的策略是智胜那些拥有八九位数资金的人，请重新考虑
要么与他们合作，要么保持距离
尊重市场参与者——他们掌握着市场走向
像保护生命一样保护你的盈利
尽可能取出本金加1倍利润
让其他资金要么暴涨要么暴跌，但要尽早锁定你的生存
保留的资金就是未来的选择权
永远不要忘记，游戏是反作用的
关注度决定价格，价格反过来又会吸引更多关注
如果没人谈论你的币，那可能还没到时候
如果人人都谈论你的币——那可能就太晚了
玩好游戏才能继续留在场上
不要过度杠杆，不要持仓过久，不要想太多
少交易，更有效地轮动，更明智地退出
加密货币奖励的是行动，而不是执着

"""

    try:
        messages = [
            {"content": "你是一个专业、客观的加密货币社区评论员。", "role": "system"},
            {"content": prompt, "role": "user"}
        ]
        comment = llm.chat(
            model_type="chat_model",
            messages=messages,
            max_tokens=300
        )
        return comment.strip()
    except Exception as e:
        logger.error(f"LLM 生成评论失败: {e}")
        return "感谢分享！"


def comment_post(page: Page, post_info: Dict, comment_text: str) -> bool:
    """评论单个 post"""
    try:
        post_card = post_info.get('card')
        if not post_card:
            logger.warning("无法获取 post card 元素")
            return False

        post_card.scroll_into_view_if_needed()

        comment_btn = post_card.locator('.footer-function-grid .comments-icon svg')
        comment_btn.click()
        logger.debug("已点击评论按钮")
        
        time.sleep(2)
        
        comment_input = page.locator('.feed-comment-input-textarea')
        if comment_input.count() > 0:
            comment_input.last.click()
            page.keyboard.type(comment_text)
            logger.debug("已填写评论内容")
            time.sleep(0.5)
        
        comment_submit = page.locator('.feed-comment-input-submit-btn').last
        comment_submit.click()

        time.sleep(0.5)

        confirm_modal = page.locator(".confirm-modal")
        if confirm_modal.count() >0 and "仅限关注" in confirm_modal.text_content():
            page.locator(".confirm-modal-cancel").click()

        return True
        
    except Exception as e:
        logger.warning(f"评论失败: {e}")
        return False


def process_square(page: Page):
    """处理 Binance Square 页面"""

    posts = get_posts_from_page(page)
    logger.info(f"共获取 {len(posts)} 个 posts")
    
    for post_info in reversed(posts):
        logger.info(f"分析 post: {post_info['content'][:20]}...")
        
        comment_text = analyze_post_with_llm(post_info)
        logger.info(f"生成评论: {comment_text}")
        
        success = comment_post(page, post_info, comment_text)
        
        if not success:
            logger.warning(f"评论 post {post_info['index']} 失败，跳过")
        
        time.sleep(10)
    
    logger.info("评论任务完成")


def main():
    """主函数"""
    logger.info("开始 Binance Square 评论任务...")
    
    def run(page: Page):
        process_square(page)
    
    open_page(SQUARE_URL, run, page_index=0)


if __name__ == "__main__":
    main()
