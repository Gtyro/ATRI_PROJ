import os
import yaml
import logging
config_path = "data/memory_config.yaml"

def check_config():
    # 检查配置文件是否存在
    if not os.path.exists("data"):
        os.makedirs("data")
        
    if not os.path.exists("data/memory_config.yaml"):
        default_config = {
            "api_key": "your_api_key_here",
            "model": "deepseek-chat",
            "api_base": "https://api.deepseek.com",
            "use_postgres": False,
            "postgres_config": {
                "host": "localhost",
                "port": 5432,
                "user": "postgres",
                "password": "password",
                "database": "memories"
            },
            "short_term_capacity": 100,
            "decay_rate": 0.05,
            "emotion_weight": 0.3,
            "access_boost": 0.1,
            "default_retention": 0.7,
            "batch_interval": 3600,
            "batch_size": 50,          # 每次批处理的消息数量
            "history_limit": 10,       # 保留给AI回复的历史消息数量
            "queue_history_size": 20   # 每个对话保留在队列中的历史消息数量
        }
        
        try:
            with open("data/memory_config.yaml", 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            logging.info("已创建默认配置文件")
        except Exception as e:
            logging.error(f"创建配置文件失败: {e}")


def load_config() -> dict:
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logging.error(f"读取配置文件失败: {e}")
        return {}
