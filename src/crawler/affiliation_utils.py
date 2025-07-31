import re
from typing import Optional, Tuple, List
from difflib import SequenceMatcher
import unicodedata


class AffiliationNormalizer:
    """机构名称标准化工具类"""
    
    # 常见的机构类型缩写映射
    INSTITUTION_ABBREVIATIONS = {
        'univ': 'university',
        'u': 'university',
        'coll': 'college',
        'inst': 'institute',
        'hosp': 'hospital',
        'med': 'medical',
        'sch': 'school',
        'dept': 'department',
        'div': 'division',
        'lab': 'laboratory',
        'ctr': 'center',
        'cntr': 'center',
        'fac': 'faculty',
        'res': 'research',
        'natl': 'national',
        'intl': 'international',
        'sci': 'science',
        'tech': 'technology',
        'eng': 'engineering',
        'bio': 'biology',
        'chem': 'chemistry',
        'phys': 'physics',
        'math': 'mathematics',
        'comp': 'computer',
        'elec': 'electrical',
        'mech': 'mechanical'
    }
    
    # 需要保留的介词和连词
    KEEP_WORDS = {'of', 'and', 'for', 'the', 'in', 'at', 'on'}
    
    # 国家和地区的标准化映射
    COUNTRY_MAPPING = {
        'usa': 'united states',
        'u.s.a': 'united states',
        'u.s.a.': 'united states',
        'us': 'united states',
        'u.s': 'united states',
        'u.s.': 'united states',
        'uk': 'united kingdom',
        'u.k': 'united kingdom',
        'u.k.': 'united kingdom',
        'pr china': 'china',
        'p.r. china': 'china',
        'peoples r china': 'china',
        "people's republic of china": 'china',
        'republic of korea': 'south korea',
        'rok': 'south korea'
    }
    
    @classmethod
    def normalize(cls, affiliation_text: str) -> str:
        """
        标准化机构名称
        
        Args:
            affiliation_text: 原始机构文本
        
        Returns:
            标准化后的机构名称
        """
        if not affiliation_text:
            return ""
        
        # 转换为小写
        text = affiliation_text.lower()
        
        # 移除多余的空白字符
        text = ' '.join(text.split())
        
        # 移除 Unicode 特殊字符
        text = cls._remove_accents(text)
        
        # 标准化标点符号
        text = cls._normalize_punctuation(text)
        
        # 展开缩写
        text = cls._expand_abbreviations(text)
        
        # 标准化国家名称
        text = cls._normalize_country_names(text)
        
        # 移除邮政编码
        text = cls._remove_postal_codes(text)
        
        # 移除电子邮件
        text = re.sub(r'\S+@\S+', '', text)
        
        # 再次清理多余空格
        text = ' '.join(text.split())
        
        return text.strip()
    
    @classmethod
    def extract_components(cls, affiliation_text: str) -> dict:
        """
        从机构文本中提取结构化信息
        
        Args:
            affiliation_text: 机构文本
        
        Returns:
            包含部门、机构、城市、国家等信息的字典
        """
        components = {
            'department': None,
            'institution': None,
            'city': None,
            'state': None,
            'country': None,
            'postal_code': None
        }
        
        # 提取邮政编码
        postal_match = re.search(r'\b\d{5,6}\b|\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b', affiliation_text)
        if postal_match:
            components['postal_code'] = postal_match.group()
        
        # 提取电子邮件域名作为机构线索
        email_match = re.search(r'@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', affiliation_text)
        if email_match:
            components['email_domain'] = email_match.group(1)
        
        # 分割成部分（通常用逗号分隔）
        parts = [p.strip() for p in affiliation_text.split(',')]
        
        if parts:
            # 第一部分通常是部门
            if any(keyword in parts[0].lower() for keyword in ['department', 'dept', 'division', 'div', 'laboratory', 'lab', 'center', 'institute']):
                components['department'] = parts[0]
                if len(parts) > 1:
                    components['institution'] = parts[1]
            else:
                components['institution'] = parts[0]
            
            # 最后一部分通常是国家
            if len(parts) > 1:
                last_part = parts[-1].strip()
                # 检查是否是已知的国家
                normalized_country = cls._normalize_country_names(last_part.lower())
                if normalized_country != last_part.lower():
                    components['country'] = normalized_country
        
        return components
    
    @classmethod
    def calculate_similarity(cls, affiliation1: str, affiliation2: str) -> float:
        """
        计算两个机构名称的相似度
        
        Args:
            affiliation1: 第一个机构名称
            affiliation2: 第二个机构名称
        
        Returns:
            相似度分数 (0-1)
        """
        # 标准化两个名称
        norm1 = cls.normalize(affiliation1)
        norm2 = cls.normalize(affiliation2)
        
        # 如果标准化后完全相同
        if norm1 == norm2:
            return 1.0
        
        # 提取组件进行比较
        comp1 = cls.extract_components(affiliation1)
        comp2 = cls.extract_components(affiliation2)
        
        # 如果机构名称相同且国家相同，认为是同一机构
        if (comp1['institution'] and comp2['institution'] and 
            cls._string_similarity(comp1['institution'], comp2['institution']) > 0.85 and
            comp1['country'] == comp2['country']):
            return 0.9
        
        # 计算基本的字符串相似度
        base_similarity = cls._string_similarity(norm1, norm2)
        
        # 如果包含相同的关键词（如大学名），提高相似度
        keywords1 = set(norm1.split())
        keywords2 = set(norm2.split())
        
        # 找出重要的共同关键词
        important_common = keywords1 & keywords2 - cls.KEEP_WORDS
        if len(important_common) >= 2:
            base_similarity = min(1.0, base_similarity + 0.2)
        
        return base_similarity
    
    @classmethod
    def is_same_institution(cls, affiliation1: str, affiliation2: str, threshold: float = 0.85) -> bool:
        """
        判断两个机构名称是否指向同一机构
        
        Args:
            affiliation1: 第一个机构名称
            affiliation2: 第二个机构名称
            threshold: 相似度阈值
        
        Returns:
            是否为同一机构
        """
        similarity = cls.calculate_similarity(affiliation1, affiliation2)
        return similarity >= threshold
    
    @staticmethod
    def _remove_accents(text: str) -> str:
        """移除重音符号"""
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
    
    @staticmethod
    def _normalize_punctuation(text: str) -> str:
        """标准化标点符号"""
        # 统一引号
        text = re.sub(r'[""''`´]', "'", text)
        # 统一破折号
        text = re.sub(r'[—–]', '-', text)
        # 移除多余的标点
        text = re.sub(r'[^\w\s,.\'-]', ' ', text)
        # 标准化缩写的点
        text = re.sub(r'\.(?=[a-z])', '. ', text)
        return text
    
    @classmethod
    def _expand_abbreviations(cls, text: str) -> str:
        """展开常见缩写"""
        words = text.split()
        expanded_words = []
        
        for word in words:
            # 移除尾部的点
            clean_word = word.rstrip('.')
            
            # 如果是已知的缩写，展开它
            if clean_word in cls.INSTITUTION_ABBREVIATIONS:
                expanded_words.append(cls.INSTITUTION_ABBREVIATIONS[clean_word])
            else:
                expanded_words.append(word)
        
        return ' '.join(expanded_words)
    
    @classmethod
    def _normalize_country_names(cls, text: str) -> str:
        """标准化国家名称"""
        for abbr, full_name in cls.COUNTRY_MAPPING.items():
            # 使用单词边界确保完整匹配
            pattern = r'\b' + re.escape(abbr) + r'\b'
            text = re.sub(pattern, full_name, text, flags=re.IGNORECASE)
        return text
    
    @staticmethod
    def _remove_postal_codes(text: str) -> str:
        """移除邮政编码"""
        # 移除5-6位数字（美国、中国等邮编）
        text = re.sub(r'\b\d{5,6}\b', '', text)
        # 移除英国邮编格式
        text = re.sub(r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b', '', text, flags=re.IGNORECASE)
        return text
    
    @staticmethod
    def _string_similarity(str1: str, str2: str) -> float:
        """计算两个字符串的相似度"""
        return SequenceMatcher(None, str1, str2).ratio()
    
    @classmethod
    def find_best_match(cls, affiliation: str, candidates: List[Tuple[int, str]], threshold: float = 0.85) -> Optional[int]:
        """
        从候选列表中找到最佳匹配的机构
        
        Args:
            affiliation: 要匹配的机构名称
            candidates: 候选机构列表，格式为 [(id, name), ...]
            threshold: 匹配阈值
        
        Returns:
            最佳匹配的机构ID，如果没有找到则返回 None
        """
        best_match_id = None
        best_similarity = 0.0
        
        for candidate_id, candidate_name in candidates:
            similarity = cls.calculate_similarity(affiliation, candidate_name)
            if similarity > best_similarity and similarity >= threshold:
                best_similarity = similarity
                best_match_id = candidate_id
        
        return best_match_id