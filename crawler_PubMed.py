import os
import time
import requests
from bs4 import BeautifulSoup
import re
import cloudscraper
import xml.etree.ElementTree as ET
import json
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/XX Safari/YY'
}

scraper = cloudscraper.create_scraper()
DOWNLOAD_DIR = 'YOUR_DIR'

QUERY = ''
FILTER_PARAM = 'simsearch2.ffrft'
PAGE_START = ''  # 起始页
PAGE_END = ''   # 结束页
MIN_SIZE_KB = #  # 最小文件大小，KB

def get_pmids(query, page=1, filter_param=None):
    # 构造带 filter 参数的搜索 URL
    url = f'https://pubmed.ncbi.nlm.nih.gov/?term={query}'
    if filter_param:
        url += f'&filter={filter_param}'
    url += f'&sort=relevance&page={page}'
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    pmids = []
    for tag in soup.find_all('a', class_='docsum-title'):
        href = tag.get('href', '')
        pmid = href.strip('/ ')
        if pmid.isdigit():
            pmids.append(pmid)
    return pmids

def get_pdf_url(pmid):
    # 使用Unpaywall API通过DOI获取开放获取PDF
    detail_url = f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/'
    resp = requests.get(detail_url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    doi_tag = soup.find('meta', attrs={'name': 'citation_doi'})
    if doi_tag and doi_tag.get('content'):
        doi = doi_tag['content']
        unpaywall_api = f"https://api.unpaywall.org/v2/{doi}?email=YOUR_EMAIL"
        try:
            ua_resp = requests.get(unpaywall_api, timeout=10)
            ua_data = ua_resp.json()
            best_loc = ua_data.get('best_oa_location') or {}
            pdf_link = best_loc.get('url_for_pdf')
            if pdf_link:
                return pdf_link
        except Exception:
            pass
    return None

def get_metadata(pmid):
    detail_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    resp = requests.get(detail_url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    metadata = {}
    # 采集所有 citation_ 开头的 meta
    for tag in soup.find_all('meta', attrs={'name': re.compile('^citation_')}):
        key = tag['name'].replace('citation_', '')
        metadata[key] = tag.get('content', '')
    # 获取摘要内容
    div = soup.find('div', class_='abstract')
    if div:
        metadata['abstract'] = div.get_text(separator=' ').strip()
    return metadata

def download_pdf(url, save_path):
    try:
        # 优先使用 cloudscraper 下载
        resp = scraper.get(url, headers=headers, timeout=30)
    except Exception:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            print(f'下载失败 {url}: {e}')
            return 0
    try:
        with open(save_path, 'wb') as f:
            f.write(resp.content)
        size = os.path.getsize(save_path)
        return size
    except Exception as e:
        print(f'写入文件失败 {save_path}: {e}')
        # 删除可能损坏的文件
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except:
                pass
        return 0

def main():
    # 创建下载目录
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # 用于保存下载成功的文献信息
    records = []
    # 聚合各页 PMIDs
    pmids_all = []
    for page in range(PAGE_START, PAGE_END + 1):
        pmids_all.extend(get_pmids(QUERY, page=page, filter_param=FILTER_PARAM))
    # 去重保持顺序
    seen = set()
    pmids = [x for x in pmids_all if not (x in seen or seen.add(x))]
    # 下载 PDF 并按大小过滤
    for pmid in pmids:
        pdf_url = get_pdf_url(pmid)
        if not pdf_url:
            print(f'{pmid} 未找到开放获取 PDF')
            continue
        ext = os.path.splitext(pdf_url.split('?')[0])[1] or '.pdf'
        save_path = os.path.join(DOWNLOAD_DIR, f'{pmid}{ext}')
        print(f'[{pmid}] 下载中: {pdf_url}')
        size = download_pdf(pdf_url, save_path)
        if size == 0:
            print(f'[{pmid}] 下载或写入失败，已跳过')
            continue
        size_kb = size / 1024
        if size_kb < MIN_SIZE_KB:
            try:
                os.remove(save_path)
            except:
                pass
            print(f'[{pmid}] PDF 大小 {size_kb:.1f}KB < {MIN_SIZE_KB}KB，已删除')
            continue
        print(f'[{pmid}] 下载完成，大小 {size_kb:.1f}KB')
        # 成功下载后采集并记录文献信息
        meta = get_metadata(pmid)
        records.append({
            'pmid': pmid,
            'pdf_url': pdf_url,
            'file_path': save_path,
            'metadata': meta
        })
        time.sleep(1)
    # 合并已有 records.json 中的记录，避免覆盖
    json_path = os.path.expanduser("~/Desktop/records.json")
    existing = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = []
    # 去重合并
    existing_pmids = set(rec.get('pmid') for rec in existing if isinstance(rec, dict))
    for rec in records:
        if rec.get('pmid') not in existing_pmids:
            existing.append(rec)
    # 写入合并后的 records
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f'已保存 {len(existing)} 条文献信息到 {json_path}')

if __name__ == '__main__':
    main()
