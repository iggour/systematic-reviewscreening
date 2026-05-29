"""
文献AI筛选工具 - Systematic Review Screening Assistant
====================================================
用Gemini API对RIS/NBIB格式的文献进行自动筛选和数据提取。

使用方法：
1. 把所有文献文件(.ris, .nbib)放进 input 文件夹
2. 在 config.py 中填入你的 Gemini API Key
3. 运行: python screen.py
4. 结果在 output 文件夹中
"""

import os
import re
import csv
import json
import time
import hashlib
import sys
from pathlib import Path

# 导入配置
from config import GEMINI_API_KEY, MODEL_NAME, REQUESTS_PER_MINUTE, TEST_MODE, TEST_COUNT

# ============================================================
# 第一部分：文献解析器（RIS / NBIB）
# ============================================================

def parse_ris(filepath):
    """解析RIS格式文件（Embase / IEEE）"""
    records = []
    current = {}
    current_tag = None
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 记录结束
            if line.startswith('ER  -'):
                if current:
                    records.append(current)
                current = {}
                current_tag = None
                continue
            
            # 新字段
            match = re.match(r'^([A-Z][A-Z0-9])  - (.*)$', line)
            if match:
                tag, value = match.group(1), match.group(2).strip()
                current_tag = tag
                
                # 多值字段（作者等）追加
                if tag in ('AU', 'A1', 'KW'):
                    if tag not in current:
                        current[tag] = []
                    current[tag].append(value)
                elif tag in current:
                    # 某些字段可能重复出现，拼接
                    current[tag] = current[tag] + ' ' + value
                else:
                    current[tag] = value
            elif current_tag and line.startswith('      '):
                # 续行（缩进的内容属于上一个字段）
                if isinstance(current.get(current_tag), list):
                    current[current_tag][-1] += ' ' + line.strip()
                elif current_tag in current:
                    current[current_tag] += ' ' + line.strip()
    
    # 最后一条可能没有ER结尾
    if current:
        records.append(current)
    
    # 统一字段名
    unified = []
    for r in records:
        title = r.get('TI') or r.get('T1') or ''
        abstract = r.get('AB') or r.get('N2') or ''
        doi = r.get('DO') or ''
        year = r.get('PY') or r.get('Y1') or r.get('DA') or ''
        # 提取年份数字
        year_match = re.search(r'(19|20)\d{2}', str(year))
        year = year_match.group(0) if year_match else year
        
        authors = r.get('AU') or r.get('A1') or []
        if isinstance(authors, str):
            authors = [authors]
        first_author = authors[0] if authors else ''
        
        journal = r.get('JF') or r.get('JO') or r.get('T2') or ''
        pub_type = r.get('TY') or ''
        
        # 来源标识
        source = 'embase' if r.get('DB') else 'ieee' if r.get('T2') else 'unknown'
        if 'Embase' in str(r.get('DB', '')):
            source = 'embase'
        
        unified.append({
            'title': title.strip(),
            'abstract': abstract.strip(),
            'doi': doi.strip(),
            'year': year.strip(),
            'first_author': first_author.strip(),
            'journal': journal.strip(),
            'pub_type': pub_type.strip(),
            'source_db': source,
            'raw_id': r.get('U2') or r.get('DO') or title[:50]
        })
    
    return unified


def parse_nbib(filepath):
    """解析PubMed NBIB格式文件"""
    records = []
    current = {}
    current_tag = None
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            
            # 记录分隔（空行）
            if line.strip() == '' and current:
                # NBIB用空行分隔记录（有时）
                continue
            
            # PMID开始新记录
            if line.startswith('PMID-'):
                if current and current.get('PMID'):
                    records.append(current)
                current = {}
                current_tag = 'PMID'
                current['PMID'] = line[5:].strip()
                continue
            
            # 新字段
            match = re.match(r'^([A-Z][A-Z0-9]*)\s*- (.*)$', line)
            if match:
                tag, value = match.group(1).strip(), match.group(2).strip()
                current_tag = tag
                
                if tag in ('AU', 'FAU', 'MH', 'OT'):
                    if tag not in current:
                        current[tag] = []
                    current[tag].append(value)
                elif tag in current:
                    current[tag] = current[tag] + ' ' + value
                else:
                    current[tag] = value
            elif current_tag and (line.startswith('      ') or line.startswith('     ')):
                # 续行
                if isinstance(current.get(current_tag), list):
                    current[current_tag][-1] += ' ' + line.strip()
                elif current_tag in current:
                    current[current_tag] += ' ' + line.strip()
    
    if current and current.get('PMID'):
        records.append(current)
    
    # 统一字段名
    unified = []
    for r in records:
        title = r.get('TI') or ''
        abstract = r.get('AB') or ''
        
        # DOI从LID字段提取
        doi = ''
        lid = r.get('LID') or ''
        doi_match = re.search(r'(10\.\S+)\s*\[doi\]', lid)
        if doi_match:
            doi = doi_match.group(1)
        
        year = r.get('DP') or ''
        year_match = re.search(r'(19|20)\d{2}', str(year))
        year = year_match.group(0) if year_match else year
        
        authors = r.get('AU') or r.get('FAU') or []
        if isinstance(authors, str):
            authors = [authors]
        first_author = authors[0] if authors else ''
        
        journal = r.get('JT') or r.get('TA') or ''
        pub_type = r.get('PT') or ''
        
        unified.append({
            'title': title.strip(),
            'abstract': abstract.strip(),
            'doi': doi.strip(),
            'year': year.strip(),
            'first_author': first_author.strip(),
            'journal': journal.strip(),
            'pub_type': pub_type.strip(),
            'source_db': 'pubmed',
            'raw_id': r.get('PMID') or doi or title[:50]
        })
    
    return unified


def load_all_records(input_dir):
    """加载input文件夹中所有文献文件"""
    all_records = []
    input_path = Path(input_dir)
    
    for filepath in sorted(input_path.iterdir()):
        if filepath.suffix.lower() == '.ris':
            print(f"  解析RIS文件: {filepath.name}")
            records = parse_ris(filepath)
            print(f"    -> {len(records)} 条记录")
            all_records.extend(records)
        elif filepath.suffix.lower() == '.nbib':
            print(f"  解析NBIB文件: {filepath.name}")
            records = parse_nbib(filepath)
            print(f"    -> {len(records)} 条记录")
            all_records.extend(records)
        elif filepath.suffix.lower() in ('.csv', '.xls', '.xlsx'):
            print(f"  跳过: {filepath.name} (请转换为RIS格式后再使用)")
    
    return all_records


def deduplicate(records):
    """基于DOI和标题去重"""
    seen_doi = set()
    seen_title = set()
    unique = []
    dup_count = 0
    
    for r in records:
        # DOI去重
        doi = r['doi'].lower().strip()
        if doi and doi in seen_doi:
            dup_count += 1
            continue
        
        # 标题去重（标准化后比较）
        title_norm = re.sub(r'[^a-z0-9]', '', r['title'].lower())
        if title_norm and title_norm in seen_title:
            dup_count += 1
            continue
        
        if doi:
            seen_doi.add(doi)
        if title_norm:
            seen_title.add(title_norm)
        unique.append(r)
    
    return unique, dup_count


# ============================================================
# 第二部分：Gemini API 调用
# ============================================================

SYSTEM_PROMPT = """You are a systematic review screening assistant. Your job is to screen research articles for a scoping review on "AI in Quantitative Neuroimaging of Pediatric Developmental Brain Disorders."

## INCLUSION CRITERIA (ALL must be met):
1. **Topic**: Uses AI/machine learning applied to neuroimaging data analysis
2. **Population**: Pediatric (≤18 years). Note: If the study focuses on a neurodevelopmental disorder (e.g., ASD, ADHD, epilepsy, cerebral palsy) and does not explicitly state the age range, it is LIKELY pediatric — mark as INCLUDE with a note "age inferred from condition"
3. **Condition**: Neurodevelopmental disorders (ASD, ADHD, epilepsy, developmental delay, cerebral palsy, intellectual disability, dyslexia, Tourette syndrome, etc.)
4. **Imaging modality**: MRI, fMRI, DTI/diffusion imaging, PET, or other structural/functional neuroimaging
5. **Methods**: Machine learning or deep learning methods used for data ANALYSIS (not just preprocessing). Includes: SVM, random forest, extra trees, gradient boosting, CNN, RNN, LSTM, transformer, autoencoder, GAN, graph neural network, ensemble methods, etc.
6. **Study type**: Original research, journal article, or full conference paper
7. **Year**: 2015-2025

## EXCLUSION CRITERIA (ANY one = exclude):
1. **Non-AI methods only**: Studies using ONLY traditional statistical methods (ICA, PCA, GLM, SEM, path analysis, t-test, ANOVA, regression without ML) — HOWEVER, if these are used for preprocessing and ML/DL is used for the main analysis, INCLUDE
2. **Non-neuroimaging**: EEG-only, genetics-only, behavioral-only, molecular biology
3. **Non-pediatric**: Adult-only populations (≥18), elderly, or animal studies
4. **Non-developmental**: Neurodegenerative diseases (Alzheimer's, Parkinson's), traumatic brain injury, stroke, tumors in adults
5. **Publication type**: Review, meta-analysis, conference abstract (not full paper), editorial, letter, book chapter, protocol
6. **No data analysis**: Theoretical/conceptual papers without actual data analysis

## IMPORTANT JUDGMENT RULES:
- Neurodevelopmental conditions (ASD, ADHD, developmental delay, childhood epilepsy) strongly imply pediatric population even if age is not stated
- "MRI" includes all variants: structural MRI, T1-weighted, T2-weighted, FLAIR, etc.
- "fMRI" includes resting-state fMRI and task-based fMRI
- "DTI" includes all diffusion imaging: DWI, HARDI, tractography
- If a study includes BOTH pediatric and adult participants, INCLUDE it
- If a study uses ML/DL on non-imaging features (e.g., clinical scores) combined with imaging, INCLUDE it
- Transfer learning, data augmentation, and federated learning studies are INCLUDED if they involve neuroimaging + ML/DL

## OUTPUT FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no explanation), with these fields:

{
  "decision": "include" | "exclude" | "uncertain",
  "reason": "Brief 1-2 sentence justification",
  "confidence": 0.0-1.0,
  "title": "article title",
  "doi": "DOI if available",
  "first_author": "first author name",
  "year": "publication year",
  "country": "country of first/corresponding author if detectable, else NR",
  "sample_size": "total N if mentioned, else NR",
  "age_range": "age range if mentioned, else NR",
  "disease": "specific condition (e.g., ASD, ADHD), else NR",
  "ai_method": "specific method (e.g., CNN, SVM, random forest), else NR",
  "method_category": "deep_learning | machine_learning | hybrid | NR",
  "deep_learning_flag": true | false,
  "modality": "MRI | fMRI | DTI | PET | multimodal | NR",
  "task": "classification | prediction | segmentation | clustering | feature_extraction | other | NR",
  "accuracy": "reported accuracy if any, else NR",
  "auc": "reported AUC if any, else NR",
  "public_dataset": "dataset name if mentioned (e.g., ABIDE, ADHD-200), else NR",
  "multimodal_flag": true | false,
  "age_inferred": true | false
}
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": """Screen this article:
Title: The first description of CTNNB1 syndrome in the Tunisian population: clinical investigation, molecular docking and molecular dynamics simulation of β-catenin/E-cadherin complex
Abstract: Background: CTNNB1 syndrome is a rare disorder caused by pathogenic variants of CTNNB1 gene, resulting in intellectual disability, peripheral spasticity, cognitive and motor impairments. The CTNNB1 encodes the β-catenin protein... In this study, we describe for the first time a CTNNB1 syndrome in Tunisian children, by the description of two unrelated Tunisian patients with spastic paraplegia, intellectual disability and visual defect using whole exome sequencing. We identified a de novo nonsense mutation... molecular docking and molecular dynamics simulations...
Year: 2026 | DOI: 10.1007/s11033-025-11182-y | Authors: Kharrat, M."""
    },
    {
        "role": "model",
        "content": json.dumps({
            "decision": "exclude",
            "reason": "Molecular biology/genetics study using whole exome sequencing and molecular docking. No neuroimaging data and no AI/ML methods applied to imaging.",
            "confidence": 0.98,
            "title": "The first description of CTNNB1 syndrome in the Tunisian population",
            "doi": "10.1007/s11033-025-11182-y",
            "first_author": "Kharrat, M.",
            "year": "2026",
            "country": "Tunisia",
            "sample_size": "2",
            "age_range": "NR",
            "disease": "CTNNB1 syndrome",
            "ai_method": "NR",
            "method_category": "NR",
            "deep_learning_flag": False,
            "modality": "NR",
            "task": "NR",
            "accuracy": "NR",
            "auc": "NR",
            "public_dataset": "NR",
            "multimodal_flag": False,
            "age_inferred": False
        }, ensure_ascii=False)
    },
    {
        "role": "user",
        "content": """Screen this article:
Title: Hybrid Deep Learning Classification Model for Attention-Deficit-Hyperactivity Disorder using functional Magnetic Resonance Imaging
Abstract: A child with a neurodevelopmental disorder, such as attention deficit hyperactivity disorder (ADHD), faces many challenges in school... a hybrid 3D convolutional neural network and bidirectional long short-term memory (3D CNN-BiLSTM) classification model is proposed to classify ADHD and typically developing conditions using resting-state functional magnetic resonance imaging of the brain. The result shows that the accuracy of the proposed hybrid deep learning model gives a maximum accuracy of 75.4% on validation... functional magnetic resonance imaging dataset obtained from the ADHD-200 repository.
Year: 2023 | DOI: 10.1109/ICISCoIS56541.2023.10100467 | Authors: U. R. K"""
    },
    {
        "role": "model",
        "content": json.dumps({
            "decision": "include",
            "reason": "Deep learning (3D CNN-BiLSTM) applied to resting-state fMRI for ADHD classification in children. Meets all inclusion criteria.",
            "confidence": 0.99,
            "title": "Hybrid Deep Learning Classification Model for ADHD using fMRI",
            "doi": "10.1109/ICISCoIS56541.2023.10100467",
            "first_author": "U. R. K",
            "year": "2023",
            "country": "NR",
            "sample_size": "NR",
            "age_range": "NR",
            "disease": "ADHD",
            "ai_method": "3D CNN-BiLSTM",
            "method_category": "deep_learning",
            "deep_learning_flag": True,
            "modality": "fMRI",
            "task": "classification",
            "accuracy": "75.4%",
            "auc": "NR",
            "public_dataset": "ADHD-200",
            "multimodal_flag": False,
            "age_inferred": True
        }, ensure_ascii=False)
    }
]


def call_gemini(title, abstract, year, doi, authors, retries=3):
    """调用Gemini API进行筛选"""
    import urllib.request
    import urllib.error
    
    user_message = f"""Screen this article:
Title: {title}
Abstract: {abstract if abstract else '[No abstract available]'}
Year: {year} | DOI: {doi} | Authors: {authors}"""
    
    # 构建请求
    messages = FEW_SHOT_EXAMPLES + [{"role": "user", "content": user_message}]
    
    payload = {
        "contents": [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            # 提取文本
            text = result['candidates'][0]['content']['parts'][0]['text']
            
            # 解析JSON
            text = text.strip()
            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
            
            parsed = json.loads(text)
            return parsed
            
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            if e.code == 429:
                # 速率限制，等待后重试
                wait = (attempt + 1) * 30
                print(f"    ⚠ 速率限制，等待{wait}秒后重试...")
                time.sleep(wait)
            elif e.code == 400:
                print(f"    ✗ 请求错误: {error_body[:200]}")
                return {"decision": "error", "reason": f"API error 400: {error_body[:100]}"}
            else:
                print(f"    ✗ HTTP错误 {e.code}: {error_body[:200]}")
                if attempt < retries - 1:
                    time.sleep(5)
        except json.JSONDecodeError as e:
            print(f"    ✗ JSON解析失败 (尝试 {attempt+1}/{retries})")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return {"decision": "error", "reason": f"JSON parse error: {str(e)}"}
        except Exception as e:
            print(f"    ✗ 错误: {str(e)}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return {"decision": "error", "reason": str(e)}
    
    return {"decision": "error", "reason": "Max retries exceeded"}


# ============================================================
# 第三部分：主流程
# ============================================================

# CSV输出字段
OUTPUT_FIELDS = [
    'id', 'source_db', 'decision', 'reason', 'confidence',
    'title', 'doi', 'first_author', 'year', 'country',
    'sample_size', 'age_range', 'disease',
    'ai_method', 'method_category', 'deep_learning_flag',
    'modality', 'task', 'accuracy', 'auc',
    'public_dataset', 'multimodal_flag', 'age_inferred',
    'journal', 'pub_type'
]


def load_progress(progress_file):
    """加载已完成的记录（支持断点续传）"""
    done = set()
    if os.path.exists(progress_file):
        with open(progress_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                done.add(row.get('id', ''))
    return done


def get_record_id(record):
    """为每条记录生成唯一ID"""
    key = (record['doi'] or record['title']).lower().strip()
    return hashlib.md5(key.encode('utf-8')).hexdigest()[:12]


def main():
    print("=" * 60)
    print("  文献AI筛选工具 v1.0")
    print("  Systematic Review Screening with Gemini AI")
    print("=" * 60)
    
    # 检查API Key
    if not GEMINI_API_KEY or GEMINI_API_KEY == 'YOUR_API_KEY_HERE':
        print("\n✗ 错误：请先在 config.py 中填入你的 Gemini API Key！")
        print("  获取方式：https://aistudio.google.com/app/apikey")
        sys.exit(1)
    
    # 设置路径
    base_dir = Path(__file__).parent
    input_dir = base_dir / 'input'
    output_dir = base_dir / 'output'
    
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # 检查input文件夹
    input_files = list(input_dir.glob('*.ris')) + list(input_dir.glob('*.nbib'))
    if not input_files:
        print(f"\n✗ 错误：input 文件夹是空的！")
        print(f"  请把 .ris 和 .nbib 文件放进: {input_dir}")
        sys.exit(1)
    
    # 加载文献
    print(f"\n[1/4] 加载文献文件...")
    records = load_all_records(input_dir)
    print(f"  共加载 {len(records)} 条记录")
    
    # 去重
    print(f"\n[2/4] 去重...")
    records, dup_count = deduplicate(records)
    print(f"  去除 {dup_count} 条重复，剩余 {len(records)} 条")
    
    # 为每条记录生成ID
    for r in records:
        r['id'] = get_record_id(r)
    
    # 检查断点续传
    output_file = output_dir / 'screening_results.csv'
    progress = load_progress(output_file)
    remaining = [r for r in records if r['id'] not in progress]
    
    if progress:
        print(f"  发现已完成 {len(progress)} 条，还剩 {len(remaining)} 条")
    
    # 测试模式
    if TEST_MODE:
        remaining = remaining[:TEST_COUNT]
        print(f"\n  *** 测试模式：只处理前 {TEST_COUNT} 条 ***")
    
    if not remaining:
        print("\n✓ 所有文献已处理完毕！")
        print(f"  结果文件: {output_file}")
        return
    
    # 开始筛选
    print(f"\n[3/4] 开始AI筛选 ({len(remaining)} 条)...")
    print(f"  模型: {MODEL_NAME}")
    print(f"  速率: {REQUESTS_PER_MINUTE} 次/分钟")
    
    delay = 60.0 / REQUESTS_PER_MINUTE
    
    # 打开CSV（追加模式）
    file_exists = output_file.exists() and output_file.stat().st_size > 0
    csvfile = open(output_file, 'a', newline='', encoding='utf-8-sig')
    writer = csv.DictWriter(csvfile, fieldnames=OUTPUT_FIELDS)
    if not file_exists:
        writer.writeheader()
    
    include_count = 0
    exclude_count = 0
    uncertain_count = 0
    error_count = 0
    total_tokens_est = 0
    
    start_time = time.time()
    
    for i, record in enumerate(remaining):
        # 进度显示
        elapsed = time.time() - start_time
        if i > 0:
            avg_time = elapsed / i
            eta = avg_time * (len(remaining) - i)
            eta_min = int(eta // 60)
            eta_sec = int(eta % 60)
            eta_str = f"预计剩余 {eta_min}分{eta_sec}秒"
        else:
            eta_str = "计算中..."
        
        print(f"\n  [{i+1}/{len(remaining)}] {eta_str}")
        title_short = record['title'][:60] + ('...' if len(record['title']) > 60 else '')
        print(f"    标题: {title_short}")
        
        # 调用API
        result = call_gemini(
            title=record['title'],
            abstract=record['abstract'],
            year=record['year'],
            doi=record['doi'],
            authors=record['first_author']
        )
        
        # 统计
        decision = result.get('decision', 'error')
        if decision == 'include':
            include_count += 1
            symbol = '✓'
        elif decision == 'exclude':
            exclude_count += 1
            symbol = '✗'
        elif decision == 'uncertain':
            uncertain_count += 1
            symbol = '?'
        else:
            error_count += 1
            symbol = '!'
        
        print(f"    判断: {symbol} {decision} (置信度: {result.get('confidence', 'N/A')})")
        print(f"    理由: {result.get('reason', 'N/A')[:80]}")
        
        # 估算token消耗
        input_tokens = len(record['abstract']) // 4 + 500  # 粗估
        output_tokens = 200
        total_tokens_est += input_tokens + output_tokens
        
        # 写入CSV
        row = {
            'id': record['id'],
            'source_db': record['source_db'],
            'journal': record['journal'],
            'pub_type': record['pub_type'],
        }
        # 合并AI返回的字段
        for field in OUTPUT_FIELDS:
            if field not in row:
                row[field] = result.get(field, 'NR')
        
        writer.writerow(row)
        csvfile.flush()  # 每条都写入，防止中断丢失
        
        # 速率控制
        if i < len(remaining) - 1:
            time.sleep(delay)
    
    csvfile.close()
    
    # 统计报告
    total_time = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"[4/4] 筛选完成！")
    print(f"{'=' * 60}")
    print(f"  处理总数: {len(remaining)}")
    print(f"  ✓ Include:   {include_count}")
    print(f"  ✗ Exclude:   {exclude_count}")
    print(f"  ? Uncertain: {uncertain_count}")
    print(f"  ! Error:     {error_count}")
    print(f"  耗时: {int(total_time//60)}分{int(total_time%60)}秒")
    print(f"  估算token消耗: ~{total_tokens_est:,}")
    print(f"\n  结果文件: {output_file}")
    print(f"  请在Excel中打开CSV文件审核结果。")


if __name__ == '__main__':
    main()
