import httpx
import asyncio
import json
import os
from datetime import datetime

# 尝试导入AstrBot的消息事件类
try:
    # 新版AstrBot导入方式
    from astrbot.api import *
except ImportError:
    try:
        # 旧版AstrBot导入方式
        from cores.qqbot.global_object import AstrMessageEvent
    except ImportError:
        # 如果都导入失败，定义一个基本的事件类
        class AstrMessageEvent:
            def __init__(self):
                self.message_str = ""
                self.message_obj = None

class NetdiskSearchPlugin:
    """
    网盘资源搜索插件
    支持搜索多个网盘平台的资源
    """
    
    def __init__(self):
        print("网盘搜索插件已加载")
        self.api_url = "https://so.yuneu.com/open/search/disk"
        
        # 加载配置文件
        self.config = self._load_config()
        
        # 从配置文件读取设置
        self.token = self.config.get("token", "")
        self.max_results = self.config.get("max_results", 10)
        self.request_interval = self.config.get("request_interval", 3)
        self.enabled_groups = self.config.get("enabled_groups", [])
        self.admin_users = self.config.get("admin_users", [])
        
        # 请求频率限制
        self.user_last_request = {}
        
        # 统计数据
        self.search_count = 0
        
        # 验证配置
        if not self.token:
            print("⚠️ 警告：未配置API Token，请在插件管理中配置后使用")
        
    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(config_path):
            default_config = {
                "token": "",
                "max_results": 10,
                "request_interval": 3,
                "enabled_groups": [],
                "admin_users": []
            }
            self._save_config(default_config)
            return default_config
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"配置文件加载失败: {e}")
            return {
                "token": "",
                "max_results": 10,
                "request_interval": 3,
                "enabled_groups": [],
                "admin_users": []
            }
    
    def _save_config(self, config):
        """保存配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"配置文件保存失败: {e}")
            
    def info(self):
        """
        插件信息，插件的基本信息
        返回: dict, 插件信息
        """
        return {
            "name": "netdisk_search",
            "author": "YourName", 
            "version": "1.0.0",
            "description": "网盘资源搜索插件，支持多平台网盘资源搜索",
            "usage": "/搜索 关键词 [页码] [参数] | /网盘帮助 | /网盘配置"
        }
        
    def run(self, ame):
        """
        插件运行函数
        参数: ame: 消息事件对象
        返回: bool, (bool, str, str) 或 (bool, list, str)
        """
        # 兼容不同版本的消息对象
        try:
            message = ame.message_str.strip() if hasattr(ame, 'message_str') else str(ame).strip()
        except:
            return False, None
        
        # 检查是否是插件相关指令
        if not (message.startswith("/搜索") or message.startswith("/search") or 
                message.startswith("/网盘帮助") or message.startswith("/nethelp") or
                message.startswith("/网盘配置") or message.startswith("/netconfig")):
            return False, None
            
        try:
            # 配置指令（仅管理员）
            if message.startswith("/网盘配置") or message.startswith("/netconfig"):
                if self._is_admin(ame):
                    return self._handle_config(message)
                else:
                    return True, (False, "❌ 仅管理员可以使用配置功能", "netdisk_search")
                    
            # 检查Token是否配置
            if not self.token:
                return True, (False, "❌ 插件未配置API Token，请联系管理员配置", "netdisk_search")
                
            # 检查权限
            if not self._check_permission(ame):
                return True, (False, "❌ 您没有权限使用此插件", "netdisk_search")
                
            # 检查频率限制
            if not self._check_rate_limit(ame):
                return True, (False, "⏰ 请求过于频繁，请稍后再试", "netdisk_search")
                
            # 帮助指令
            if message.startswith("/网盘帮助") or message.startswith("/nethelp"):
                help_text = self._get_help_text()
                return True, (True, help_text, "netdisk_search")
                
            # 搜索指令
            if message.startswith("/搜索") or message.startswith("/search"):
                # 异步执行搜索
                result = asyncio.run(self._handle_search(message))
                if result:
                    self.search_count += 1
                    return True, (True, result, "netdisk_search")
                else:
                    return True, (False, "❌ 搜索失败，请检查参数或稍后重试", "netdisk_search")
                    
        except Exception as e:
            print(f"网盘搜索插件错误: {e}")
            return True, (False, f"❌ 插件运行出错：{str(e)}", "netdisk_search")
            
        return False, None
        
    def _handle_config(self, message: str):
        """处理配置指令"""
        parts = message.replace("/网盘配置", "").replace("/netconfig", "").strip().split()
        
        if not parts:
            # 显示当前配置
            config_text = f"""
📝 网盘搜索插件配置

🔑 API Token: {'已配置' if self.token else '未配置'}
📊 最大结果数: {self.max_results}
⏰ 请求间隔: {self.request_interval}秒
👥 启用群组: {len(self.enabled_groups)}个
👑 管理员: {len(self.admin_users)}个

💡 配置命令：
/网盘配置 token <你的token>
/网盘配置 max_results <数量>
/网盘配置 interval <秒数>
/网盘配置 add_group <群号>
/网盘配置 add_admin <用户ID>
"""
            return True, (True, config_text, "netdisk_search")
            
        if len(parts) < 2:
            return True, (False, "❌ 配置格式错误，请查看配置帮助", "netdisk_search")
            
        key = parts[0].lower()
        value = parts[1]
        
        if key == "token":
            self.config["token"] = value
            self.token = value
            self._save_config(self.config)
            return True, (True, "✅ API Token 配置成功", "netdisk_search")
            
        elif key == "max_results":
            try:
                max_results = int(value)
                if 1 <= max_results <= 50:
                    self.config["max_results"] = max_results
                    self.max_results = max_results
                    self._save_config(self.config)
                    return True, (True, f"✅ 最大结果数设置为 {max_results}", "netdisk_search")
                else:
                    return True, (False, "❌ 最大结果数必须在1-50之间", "netdisk_search")
            except ValueError:
                return True, (False, "❌ 请输入有效的数字", "netdisk_search")
                
        elif key == "interval":
            try:
                interval = int(value)
                if 1 <= interval <= 60:
                    self.config["request_interval"] = interval
                    self.request_interval = interval
                    self._save_config(self.config)
                    return True, (True, f"✅ 请求间隔设置为 {interval}秒", "netdisk_search")
                else:
                    return True, (False, "❌ 请求间隔必须在1-60秒之间", "netdisk_search")
            except ValueError:
                return True, (False, "❌ 请输入有效的数字", "netdisk_search")
                
        elif key == "add_group":
            if value not in self.config["enabled_groups"]:
                self.config["enabled_groups"].append(value)
                self.enabled_groups.append(value)
                self._save_config(self.config)
                return True, (True, f"✅ 已添加群组 {value}", "netdisk_search")
            else:
                return True, (False, "❌ 该群组已存在", "netdisk_search")
                
        elif key == "add_admin":
            if value not in self.config["admin_users"]:
                self.config["admin_users"].append(value)
                self.admin_users.append(value)
                self._save_config(self.config)
                return True, (True, f"✅ 已添加管理员 {value}", "netdisk_search")
            else:
                return True, (False, "❌ 该用户已是管理员", "netdisk_search")
                
        else:
            return True, (False, "❌ 未知配置项", "netdisk_search")
    
    def _check_permission(self, ame) -> bool:
        """检查使用权限"""
        # 如果未配置群组白名单，则允许所有群组
        if not self.enabled_groups:
            return True
            
        # 检查是否是管理员
        if self._is_admin(ame):
            return True
            
        # 检查是否在允许的群组中
        try:
            # 尝试获取群组ID，根据不同版本调整
            group_id = None
            if hasattr(ame, 'message_obj') and ame.message_obj:
                if hasattr(ame.message_obj, 'group_id'):
                    group_id = ame.message_obj.group_id
                elif hasattr(ame.message_obj, 'guild_id'):
                    group_id = ame.message_obj.guild_id
                    
            if group_id and str(group_id) in self.enabled_groups:
                return True
        except:
            pass
            
        return False
    
    def _is_admin(self, ame) -> bool:
        """检查是否是管理员"""
        try:
            # 尝试获取用户ID，兼容不同版本
            user_id = None
            if hasattr(ame, 'message_obj') and ame.message_obj:
                if hasattr(ame.message_obj, 'author') and ame.message_obj.author:
                    user_id = getattr(ame.message_obj.author, 'id', None)
                elif hasattr(ame.message_obj, 'user_id'):
                    user_id = ame.message_obj.user_id
                elif hasattr(ame.message_obj, 'sender'):
                    user_id = getattr(ame.message_obj.sender, 'user_id', None)
                    
            return str(user_id) in self.admin_users if user_id else False
        except:
            return False
        
    def _check_rate_limit(self, ame) -> bool:
        """检查请求频率限制"""
        try:
            # 尝试获取用户ID用于频率限制
            user_id = "unknown"
            if hasattr(ame, 'message_obj') and ame.message_obj:
                if hasattr(ame.message_obj, 'author') and ame.message_obj.author:
                    user_id = getattr(ame.message_obj.author, 'id', "unknown")
                elif hasattr(ame.message_obj, 'user_id'):
                    user_id = ame.message_obj.user_id
                elif hasattr(ame.message_obj, 'sender'):
                    user_id = getattr(ame.message_obj.sender, 'user_id', "unknown")
        except:
            user_id = "unknown"
            
        current_time = datetime.now().timestamp()
        
        if user_id in self.user_last_request:
            time_diff = current_time - self.user_last_request[user_id]
            if time_diff < self.request_interval:
                return False
                
        self.user_last_request[user_id] = current_time
        return True
        
    async def _handle_search(self, message: str) -> str:
        """处理搜索请求"""
        # 解析搜索参数
        params = self._parse_search_command(message)
        if not params:
            return "❌ 搜索格式错误！\n请使用：/搜索 关键词 [页码] [参数]\n发送 /网盘帮助 查看详细用法"
            
        try:
            # 执行搜索
            results = await self._search_api(params)
            if results:
                return self._format_results(results, params)
            else:
                return "❌ 搜索失败，请检查网络或稍后重试"
                
        except Exception as e:
            print(f"搜索出错: {e}")
            return f"❌ 搜索出错：{str(e)}"
            
    def _parse_search_command(self, message: str) -> dict:
        """解析搜索命令参数"""
        # 移除命令前缀
        content = message.replace("/搜索", "").replace("/search", "").strip()
        if not content:
            return None
            
        parts = content.split()
        if not parts:
            return None
            
        params = {
            "q": parts[0],  # 搜索关键词
            "page": 1,
            "size": self.max_results,
            "time": "",
            "type": "",
            "exact": False
        }
        
        # 解析其他参数
        i = 1
        while i < len(parts):
            param = parts[i].lower()
            
            # 页码
            if param.isdigit():
                params["page"] = min(int(param), 50)  # 限制最大页数
            # 时间范围
            elif param in ["week", "month", "three_month", "year", "一周", "一月", "三月", "一年"]:
                time_map = {
                    "一周": "week", "一月": "month", 
                    "三月": "three_month", "一年": "year"
                }
                params["time"] = time_map.get(param, param)
            # 资源类型
            elif param.upper() in ["BDY", "ALY", "QUARK", "XUNLEI", "百度", "阿里", "夸克", "迅雷"]:
                type_map = {
                    "百度": "BDY", "阿里": "ALY", 
                    "夸克": "QUARK", "迅雷": "XUNLEI"
                }
                params["type"] = type_map.get(param, param.upper())
            # 精确搜索
            elif param in ["exact", "精确", "准确"]:
                params["exact"] = True
                
            i += 1
            
        return params
        
    async def _search_api(self, params: dict) -> dict:
        """调用搜索API"""
        headers = {
            "Content-Type": "application/json"
        }
        
        # 添加认证头
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        # 构建请求数据
        search_data = {
            "q": params["q"],
            "page": params["page"],
            "size": params["size"],
            "time": params["time"],
            "type": params["type"],
            "exact": params["exact"]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    json=search_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"API请求失败: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            print("API请求超时")
            return None
        except Exception as e:
            print(f"API请求异常: {e}")
            return None
            
    def _format_results(self, data: dict, params: dict) -> str:
        """格式化搜索结果"""
        # 根据API实际返回格式调整
        if not data:
            return "❌ 未找到相关资源"
            
        # 假设API返回格式，你需要根据实际API调整
        success = data.get("success", data.get("status") == "ok")
        if not success:
            return "❌ 搜索请求失败"
            
        results = data.get("data", data.get("results", []))
        total = data.get("total", len(results))
        
        if not results:
            return "📭 未找到相关资源，请尝试其他关键词"
            
        # 构建回复消息
        response = f"🔍 搜索「{params['q']}」\n"
        response += f"📊 共找到 {total} 个结果，显示第 {params['page']} 页\n"
        
        if params.get("time"):
            time_desc = {
                "week": "一周内", "month": "一个月内",
                "three_month": "三个月内", "year": "一年内"
            }
            response += f"📅 时间范围：{time_desc.get(params['time'], params['time'])}\n"
            
        if params.get("type"):
            type_desc = {
                "BDY": "百度网盘", "ALY": "阿里云盘",
                "QUARK": "夸克网盘", "XUNLEI": "迅雷云盘"
            }
            response += f"💾 资源类型：{type_desc.get(params['type'], params['type'])}\n"
            
        response += "\n" + "="*30 + "\n\n"
        
        # 显示结果 - 根据实际API返回数据结构调整字段名
        for i, item in enumerate(results[:self.max_results], 1):
            title = item.get("title", item.get("name", "未知文件"))
            size = item.get("size", item.get("filesize", "未知大小"))
            source = item.get("source", item.get("platform", "未知来源"))
            link = item.get("link", item.get("url", ""))
            update_time = item.get("update_time", item.get("created_at", ""))
            
            response += f"📄 {i}. {title}\n"
            response += f"💾 大小：{size}\n"
            response += f"🔗 来源：{source}\n"
            
            if update_time:
                response += f"⏰ 更新：{update_time}\n"
                
            if link:
                response += f"🌐 链接：{link}\n"
                
            response += "\n"
            
        # 添加翻页提示
        if total > params["page"] * params["size"]:
            next_page = params["page"] + 1
            search_cmd = f"/搜索 {params['q']} {next_page}"
            if params.get("time"):
                search_cmd += f" {params['time']}"
            if params.get("type"):
                search_cmd += f" {params['type']}"
            if params.get("exact"):
                search_cmd += " exact"
                
            response += f"📄 查看下一页：{search_cmd}"
            
        return response
        
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        help_text = f"""
🔍 网盘搜索插件帮助

📝 基本用法：
/搜索 关键词 [页码] [参数]

📋 参数说明：
• 页码：1, 2, 3... (默认第1页)
• 时间：week/一周, month/一月, three_month/三月, year/一年
• 类型：BDY/百度, ALY/阿里, QUARK/夸克, XUNLEI/迅雷
• 精确：exact/精确 (精确匹配)

💡 使用示例：
/搜索 Python教程
/搜索 电影 2 month BDY
/搜索 小说 1 week exact
/搜索 纪录片 阿里 精确

❓ 其他命令：
/网盘帮助 - 显示此帮助
/网盘配置 - 插件配置（管理员）

📊 插件统计：
总搜索次数：{self.search_count}
"""
        
        return help_text


# 主类别名，AstrBot会自动识别
Main = NetdiskSearchPlugin
