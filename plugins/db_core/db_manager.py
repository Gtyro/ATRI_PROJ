import logging
from typing import Any, Dict, List, Optional, Set

from tortoise import Tortoise


class DBManager:
    _instance = None
    _initialized = False
    _db_url = None
    _registered_models = []
    
    # 内部使用，跟踪已注册模块的集合
    _registered_module_set = set()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DBManager()
        return cls._instance

    def register_models(self, app_name: str, model_modules: List[str]) -> None:
        """注册模型模块路径"""
        for module in model_modules:
            if module not in self._registered_module_set:
                self._registered_models.append((app_name, module))
                self._registered_module_set.add(module)
                logging.debug(f"已注册模型模块: {module}")
            else:
                logging.warning(f"模型模块已存在，跳过注册: {module}")

    def set_db_url(self, db_url: str) -> None:
        """设置数据库URL"""
        if self._initialized:
            logging.warning(f"数据库已初始化，忽略URL设置: {db_url}")
            return
            
        if self._db_url != db_url:
            self._db_url = db_url
            logging.info(f"已设置数据库URL: {db_url}")

    async def initialize(self, generate_schemas: bool = True) -> None:
        """初始化所有数据库连接"""
        if self._initialized:
            logging.info("数据库已经初始化，跳过")
            return

        if not self._db_url:
            raise ValueError("数据库URL未设置，请先调用set_db_url")
            
        if not self._registered_models:
            logging.warning("没有注册任何模型，数据库将不会创建任何表")

        # 构建模块字典
        modules_dict = {}
        for app_name, module in self._registered_models:
            if app_name not in modules_dict:
                modules_dict[app_name] = []
            modules_dict[app_name].append(module)

        try:
            logging.debug(f"开始初始化数据库: {self._db_url}")
            
            await Tortoise.init(
                db_url=self._db_url,
                modules=modules_dict
            )
            
            if generate_schemas:
                logging.debug(f"正在生成数据库表结构...")
                await Tortoise.generate_schemas()
                
            # 动态导入，避免循环引用
            try:
                from plugins.webui.backend.api.core.shared import \
                    table_to_model_map

                # 构建表名到模型的映射
                models = Tortoise.apps.get("models", {})
                for model_name, model in models.items():
                    table_name = model._meta.db_table
                    table_to_model_map[table_name] = model
                    
                logging.info(f"构建表名到模型的映射完成，共 {len(table_to_model_map)} 个表")
            except ImportError:
                logging.warning("无法导入table_to_model_map，跳过表映射构建")
                
            self._initialized = True
            logging.info(f"数据库初始化成功")
            
        except Exception as e:
            logging.error(f"数据库初始化失败: {e}")
            raise

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._initialized:
            await Tortoise.close_connections()
            self._initialized = False
            logging.info("数据库连接已关闭")
            
    def is_initialized(self) -> bool:
        """返回数据库是否已初始化"""
        return self._initialized
        
    def get_registered_modules(self) -> Set[str]:
        """返回已注册的模块集合"""
        return self._registered_module_set.copy()

# 全局单例实例
db_manager = DBManager.get_instance() 