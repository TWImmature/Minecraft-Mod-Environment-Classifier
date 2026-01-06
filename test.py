import shutil
from pathlib import Path
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from typing import Set, Optional, Dict, List, Union

# 加载器关键词
_LOADER_KEYWORDS: Set[str] = {"forge", "fabric", "neoforge", "quilt", "rift"}
_SUFFIX_TO_STRIP: Set[str] = {"forge", "fabric", "neoforge", "quilt", "rift"}

# 状态码映射
_STATUS_MAP = {"需装": 1, "可选": 2, "无效": 3}
_CLIENT_MAPPING = {
    1: "ClientRequired",
    2: "ClientOptional",
    3: "ClientInvalid"
}
_SERVER_MAPPING = {
    1: "ServerRequired",
    2: "ServerOptional",
    3: "ServerInvalid"
}


def check_environment_status(file_path: Path) -> Optional[List[int]]:
    """检查环境状态文件并返回状态码列表（支持单状态）"""
    try:
        content = read_file_with_fallback(file_path)  # 假设已实现该函数
        if not content:
            return None

        # 尝试匹配完整格式：运行环境: 客户端X, 服务端Y
        full_match = re.search(
            r'运行环境:\s*客户端(需装|可选|无效)\s*,\s*服务端(需装|可选|无效)',
            content
        )
        if full_match:
            return [
                _STATUS_MAP[full_match.group(1)],
                _STATUS_MAP[full_match.group(2)]
            ]

        # 尝试匹配客户端单状态
        client_match = re.search(
            r'运行环境:\s*客户端(需装|可选|无效)',
            content
        )
        # 尝试匹配服务端单状态
        server_match = re.search(
            r'运行环境:\s*服务端(需装|可选|无效)',
            content
        )

        # 处理不同组合情况
        if client_match and server_match:
            # 同时存在两个单状态（取第一个匹配项）
            return [
                _STATUS_MAP[client_match.group(1)],
                _STATUS_MAP[server_match.group(1)]
            ]
        elif client_match:
            # 仅客户端状态
            return [_STATUS_MAP[client_match.group(1)], 3]
        elif server_match:
            # 仅服务端状态
            return [3, _STATUS_MAP[server_match.group(1)]]
        else:
            return None  # 无有效状态

    except Exception as e:
        print(f"处理文件时出错: {e}")
        return None


def read_file_with_fallback(file_path: Path) -> Optional[str]:
    """尝试用不同编码读取文件内容"""
    encodings = ['utf-8', 'gbk']
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"读取文件 {file_path} 时出错: {e}")
            return None
    return None


def find_target_urls_in_folder(folder_path: Path) -> Dict[str, Optional[str]]:
    """在文件夹中查找所有TXT文件中的目标URL"""
    results = {}
    if not folder_path.is_dir():
        print(f"错误: '{folder_path}' 不是有效目录")
        return results

    for file_path in folder_path.glob('*.txt'):
        content = read_file_with_fallback(file_path)
        if not content:
            results[file_path.name] = None
            continue

        match = re.search(r'www\.mcmod\.cn/class/\d+\.html', content)
        results[file_path.name] = f"http://{match.group(0)}" if match else None

    return results


def find_target_url_in_file(file_path: Path) -> Optional[str]:
    """在单个文件中查找目标URL"""
    if not file_path.is_file() or file_path.suffix.lower() != '.txt':
        return None

    content = read_file_with_fallback(file_path)
    if not content:
        return None

    match = re.search(r'www\.mcmod\.cn/class/\d+\.html', content)
    return f"http://{match.group(0)}" if match else None


def save_webpage(url: str, file_path: Path, use_selenium: bool = False) -> bool:
    """保存网页内容到文件"""
    try:
        if use_selenium:
            return _save_with_selenium(url, file_path)
        return _save_with_requests(url, file_path)
    except Exception as e:
        print(f"保存网页出错: {e}")
        return False


def _save_with_requests(url: str, file_path: Path) -> bool:
    """使用requests保存网页"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    try:
        session = requests.Session()
        session.headers.update(headers)

        # 两次请求模拟真实访问
        session.get(url, timeout=10)
        time.sleep(1)

        response = session.get(url, timeout=15)
        response.raise_for_status()

        # 处理编码
        content = response.content.decode(response.apparent_encoding or 'utf-8', errors='ignore')

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Requests错误: {e}")
        return False


def _save_with_selenium(url: str, file_path: Path) -> bool:
    """使用Selenium保存动态网页"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(10)
        driver.get(url)
        time.sleep(2)  # 等待JS执行

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        return True
    except Exception as e:
        print(f"Selenium错误: {e}")
        return False
    finally:
        driver.quit()


def extract_jar_basename(filename: str) -> Optional[str]:
    """
    从JAR文件名提取基础名称
    在遇到版本号时停止合并，并正确处理包含数字的片段
    特别处理以"api"或"lib"结尾的名称

    参数:
        filename (str): JAR文件名

    返回:
        str: 提取的基础名称，失败时返回None
    """
    # 检查是否为JAR文件
    if not isinstance(filename, str) or not filename.lower().endswith(".jar"):
        return None

    # 仅保留文件名（不含路径）并移除扩展名
    fname = Path(filename).name
    if fname.lower().endswith(".jar"):
        fname = fname[:-4]  # 移除.jar扩展名

    # 去除 [...] 前缀（如 [JEI物品管理器]）
    fname = re.sub(r"^\[[^\]]+\]\s*", "", fname)

    # 替换特殊字符为空格（括号、标点等）
    fname = re.sub(r"[()\[\]{}@~`'\"&^%$#*=<>|\\/]", " ", fname)

    # 分割文件名（使用多种分隔符）
    parts = re.split(r"[\s_\-\+]+", fname)
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        return None

    # 合并片段直到遇到版本号或加载器标识
    merged = []
    for i, part in enumerate(parts):
        lower_part = part.lower()

        # 检查是否是加载器关键词（精确匹配）
        if any(kw == lower_part for kw in _LOADER_KEYWORDS) and i > 0:
            # 如果是加载器且在第二个位置之后，停止添加
            break

        # 改进的版本号检测模式（包含Minecraft版本号识别）
        version_patterns = [
            r'^v?\d+\.\d+(\.\d+){0,2}[a-z]*$',  # v1.2.3a, 1.2.3-beta
            r'^mc?1?\d\.\d{1,2}(\.\d+)?[a-z]*$',  # mc1.20.1, 1.20.1a
            r'^\d+(\.\d+)*[a-z]*$',  # 1.2.3a, 2023.1
            r'^\d+[a-z]+\d*$',  # 5a, 2b3
            r'^[a-z]+\d+[a-z]*$',  # alpha2, beta3
            r'^\d+$'  # 纯数字
        ]

        is_version = False
        for pattern in version_patterns:
            if re.match(pattern, lower_part):
                is_version = True
                break

        # 如果检测到版本号且已有合并内容，则停止
        if is_version and merged:
            break

        # 检查是否包含版本标识符（如pre, rc, beta等）
        version_indicators = ['pre', 'rc', 'beta', 'alpha', 'dev']
        has_version_indicator = any(indicator in lower_part for indicator in version_indicators)

        # 如果包含版本标识符且已有合并内容，并且有数字，则停止
        if has_version_indicator and merged and any(char.isdigit() for char in lower_part):
            break

        # 检查是否是纯数字片段（即使没匹配版本模式）
        if lower_part.isdigit() and merged:
            break

        # 添加到合并列表
        merged.append(part)

    # 组合名称
    candidate = " ".join(merged).strip()

    # 如果没有合并到任何内容，尝试使用第一个有效部分
    if not candidate and parts:
        candidate = parts[0]

    # 特别处理以"api"或"lib"结尾的名称
    lower_candidate = candidate.lower()
    if lower_candidate.endswith("api"):
        # 分离API后缀
        prefix = candidate[:-3].rstrip()
        # 如果前缀以's'结尾，则去除
        if prefix.endswith('s'):
            prefix = prefix[:-1].rstrip()
        candidate = f"{prefix} API"
    elif lower_candidate.endswith("lib"):
        # 分离LIB后缀
        prefix = candidate[:-3].rstrip()
        # 如果前缀以's'结尾，则去除
        if prefix.endswith('s'):
            prefix = prefix[:-1].rstrip()
        candidate = f"{prefix} Lib"

    # 去除尾部后缀（forge/fabric/neoforge）
    lower_candidate = candidate.lower()
    for suffix in _SUFFIX_TO_STRIP:
        if lower_candidate.endswith(suffix):
            idx = len(candidate) - len(suffix)
            candidate = candidate[:idx].strip()
            break

    # 清理非法字符（保留字母、数字和空格）
    candidate = re.sub(r"[^A-Za-z0-9\s]", "", candidate)

    # 处理特殊情况：移除孤立的数字（如 "naturalist 50pre3" -> "naturalist"）
    words = candidate.split()
    cleaned_words = []
    for word in words:
        # 保留纯字母单词
        if word.isalpha():
            cleaned_words.append(word)
        # 保留包含字母和数字的单词（如 "forgecraft2"）
        elif any(char.isalpha() for char in word) and any(char.isdigit() for char in word):
            cleaned_words.append(word)
        # 跳过纯数字单词（如版本号）

    candidate = " ".join(cleaned_words).strip()

    # 如果清理后为空，回退到原始合并结果
    if not candidate and merged:
        candidate = " ".join(merged).strip()

    return candidate if candidate else None


def process_jar_file(jar_path: Path, output_dir: Path) -> None:
    """处理单个JAR文件"""
    print(f"处理文件: {jar_path.name}")

    # 提取基础名称
    base_name = extract_jar_basename(jar_path.name)
    if not base_name:
        print("无法提取有效名称")
        # 确保目标目录存在
        (output_dir / "unknown").mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar_path, output_dir / "unknown" / jar_path.name)
        return

    print(f"提取名称: {base_name}")

    # 创建必要目录
    web_dir = output_dir / "webTxt"
    web_dir.mkdir(exist_ok=True)
    search_path = web_dir / f"{base_name}.txt"

    # 获取搜索结果
    search_url = f"https://search.mcmod.cn/s?key={base_name}"
    if not save_webpage(search_url, search_path, use_selenium=False):
        print("搜索失败")
        (output_dir / "unknown").mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar_path, output_dir / "unknown" / jar_path.name)
        return

    # 获取目标URL
    target_url = find_target_url_in_file(search_path)
    if not target_url:
        print("未找到目标URL")
        (output_dir / "unknown").mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar_path, output_dir / "unknown" / jar_path.name)
        return

    # 获取详情页
    if not save_webpage(target_url, search_path):
        print("详情页获取失败")
        (output_dir / "unknown").mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar_path, output_dir / "unknown" / jar_path.name)
        return

    # 检查环境状态
    statuses = check_environment_status(search_path)
    if not statuses or len(statuses) < 2:
        print("环境状态解析失败")
        (output_dir / "unknown").mkdir(parents=True, exist_ok=True)
        shutil.copy2(jar_path, output_dir / "unknown" / jar_path.name)
        return

    # 处理状态码
    client_status, server_status = statuses
    client_subdir = _CLIENT_MAPPING.get(client_status, "ClientInvalid")
    server_subdir = _SERVER_MAPPING.get(server_status, "ServerInvalid")

    client_dir = output_dir / "classified" / client_subdir
    server_dir = output_dir / "classified" / server_subdir

    # 确保目录存在
    client_dir.mkdir(parents=True, exist_ok=True)
    server_dir.mkdir(parents=True, exist_ok=True)

    # 复制文件
    shutil.copy2(jar_path, client_dir / jar_path.name)
    shutil.copy2(jar_path, server_dir / jar_path.name)
    print(f"已分类: 客户端={client_subdir}, 服务端={server_subdir}")


def organize_mods(input_dir: Union[str, Path], output_dir: Union[str, Path]) -> None:
    """主处理函数：组织MOD文件"""
    # 将输入转换为Path对象
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # 创建目录结构
    unknown_dir = output_dir / "unknown"
    unknown_dir.mkdir(parents=True, exist_ok=True)

    classified_dir = output_dir / "classified"
    classified_dir.mkdir(exist_ok=True)

    for subdir in ["ServerRequired", "ServerOptional", "ServerInvalid",
                   "ClientRequired", "ClientOptional", "ClientInvalid"]:
        (classified_dir / subdir).mkdir(exist_ok=True)

    # 处理文件
    for item in input_dir.iterdir():
        if item.is_file() and item.suffix.lower() == '.jar':
            process_jar_file(item, output_dir)
        else:
            # 非JAR文件复制到unknown
            dest = unknown_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)  # 如果目标已存在，先删除
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print('-' * 40)

organize_mods("mods", "output")
print("===end===")
