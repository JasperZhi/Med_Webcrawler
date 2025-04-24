import os
import time
import random
import requests
import logging
from urllib.parse import unquote
import re
from DrissionPage import ChromiumOptions, ChromiumPage

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 设置参数
START_PAGE = 16
END_PAGE = 17
BASE_URL = "https://guidelines.ebmportal.com/?fv%5Bfield_collection_field_4%5D%5B2942%5D=2942&fv%5Bfield_collection_field_4%5D%5B2796%5D=2796&l=50&page={}"
DOWNLOAD_DIR = "/Users/xjz/Desktop/Crawled_1"

# 创建下载目录
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def setup_browser():
    """设置浏览器配置"""
    options = ChromiumOptions()
    options.auto_port = True
    options.set_paths(browser_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    
    # 设置headless模式
    options.set_argument('--headless=new')
    options.set_argument('--disable-gpu')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-dev-shm-usage')
    
    return options

def random_delay():
    """模拟人类操作延迟"""
    time.sleep(random.uniform(1, 3))

def download_pdf(url, filename):
    """下载PDF文件"""
    try:
        # 解码URL编码的文件名
        filename = unquote(filename)
        # 移除文件名中的非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        # 确保文件名以.pdf结尾
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        # 检查文件是否已存在且有效
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            if file_size > 10240:  # 大于10KB的文件认为是有效的
                logging.info(f"文件已存在且有效: {filename} ({file_size} bytes)")
                return True
            else:
                logging.warning(f"已存在的文件过小，将重新下载: {filename} ({file_size} bytes)")
                os.remove(filepath)

        # 使用requests下载文件
        response = requests.get(url, stream=True, verify=False, timeout=30)
        response.raise_for_status()

        # 检查内容类型
        content_type = response.headers.get('content-type', '')
        if 'pdf' not in content_type.lower():
            logging.warning(f"非PDF文件: {url} (Content-Type: {content_type})")
            return False

        # 检查文件大小
        content_length = int(response.headers.get('content-length', 0))
        if content_length < 10240:  # 小于10KB的文件可能是无效的
            logging.warning(f"文件太小: {url} ({content_length} bytes)")
            return False

        # 保存文件
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logging.info(f"成功下载: {filename}")
        return True

    except Exception as e:
        logging.error(f"下载失败 {url}: {str(e)}")
        return False

def process_page(page, page_url):
    """处理单个页面"""
    try:
        page.get(page_url)
        random_delay()

        # 查找所有链接
        links = page.s_eles('a')
        pdf_links = []

        for link in links:
            try:
                href = link.attr('href')
                text = link.text.strip()
                if not href or not text:
                    continue

                # 检查是否是PDF链接或"view publication"链接
                if href.lower().endswith('.pdf') or 'pdf' in href.lower() or 'view publication' in text.lower():
                    pdf_links.append(href)
            except Exception as e:
                logging.error(f"处理链接失败: {str(e)}")
                continue

        if not pdf_links:
            logging.warning("⚠️ 未找到PDF链接")
            return 0

        logging.info(f"找到 {len(pdf_links)} 个PDF链接")
        success_count = 0
        
        for pdf_url in pdf_links:
            # 从 URL 提取真正的文件名
            filename = unquote(pdf_url.split('/')[-1])
            if download_pdf(pdf_url, filename):
                success_count += 1
            random_delay()

        return success_count

    except Exception as e:
        logging.error(f"处理页面失败 {page_url}: {str(e)}")
        return 0

def main():
    total_pages = END_PAGE - START_PAGE + 1
    total_downloads = 0
    
    # 创建主浏览器实例
    page = ChromiumPage(setup_browser())
    try:
        for page_num in range(START_PAGE, END_PAGE + 1):
            logging.info(f"\n📖 开始处理第 {page_num} 页...")
            page_url = BASE_URL.format(page_num)
            logging.info(f"\n🔍 处理主页面: {page_url}")
            
            downloads = process_page(page, page_url)
            total_downloads += downloads
            logging.info(f"本页成功下载 {downloads} 个PDF")
            random_delay()

        logging.info(f"\n🎉 全部完成！共处理 {total_pages} 页，成功下载 {total_downloads} 个PDF")
        logging.info(f"PDF已保存到 {DOWNLOAD_DIR}")
    finally:
        page.quit()

if __name__ == "__main__":
    main() 
