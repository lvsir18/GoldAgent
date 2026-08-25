"""
配置加载模块 - 管理 config.yaml 和环境变量
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from .settings import AppSettings


class ConfigLoader:
    """配置管理类"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置加载器
        
        Args:
            config_path: config.yaml 文件路径，默认为项目根目录
        """
        # 确定项目根目录
        base_dir = Path(__file__).parent.parent
        
        # 加载环境变量 - 指定 .env 文件路径，覆盖已有的环境变量
        env_path = base_dir / ".env"
        load_dotenv(dotenv_path=env_path, override=True)
        
        # 确定配置文件路径
        if config_path is None:
            config_path = base_dir / "config.yaml"
        
        self.config_path = Path(config_path)
        self.settings = AppSettings.load(self.config_path)
        self.config = self.settings.model_dump(mode="json")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载 YAML 配置文件
        
        Returns:
            配置字典
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        return AppSettings.load(self.config_path).model_dump(mode="json")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持深层路径如 'data.international.symbol'
        
        Args:
            key: 配置键，支持点号分隔的路径
            default: 默认值
        
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_env(self, key: str, default: str = None) -> str:
        """
        从环境变量获取值
        
        Args:
            key: 环境变量名
            default: 默认值
        
        Returns:
            环境变量值
        """
        return os.getenv(key, default)
    
    def get_api_key(self, api_name: str = "DASHSCOPE_API_KEY") -> str:
        """
        获取 API Key
        
        Args:
            api_name: API Key 的环境变量名
        
        Returns:
            API Key
        
        Raises:
            ValueError: 如果 API Key 不存在
        """
        api_key = self.get_env(api_name)
        if not api_key and api_name == "DASHSCOPE_API_KEY":
            api_key = self.settings.llm_api_key()
        if not api_key:
            raise ValueError(f"未配置环境变量: {api_name}，请检查 .env 文件")
        return api_key
    
    def reload(self):
        """重新加载配置"""
        self.settings = AppSettings.load(self.config_path)
        self.config = self.settings.model_dump(mode="json")


# 全局配置实例
_global_config = None


def get_config() -> ConfigLoader:
    """
    获取全局配置实例
    
    Returns:
        ConfigLoader 实例
    """
    global _global_config
    if _global_config is None:
        _global_config = ConfigLoader()
    return _global_config
