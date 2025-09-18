from datetime import datetime
import pytz

def convert_time_format(original_str):
    # 去除时区部分并替换 T 为空格
    dt_str = original_str.split('+')[0].replace('T', ' ')

    # 分离日期时间与微秒（处理 9 位微秒）
    if '.' in dt_str:
        main_part, fractional = dt_str.split('.')
        fractional = fractional.ljust(9, '0')[:6]  # 截断或补零至 6 位
        dt_str = f"{main_part}.{fractional}"
    else:
        dt_str += ".000000"

    # 解析为 datetime 对象
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")

    # 格式化为目标字符串
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

def convert_time_with_timezone(original_str, target_tz='Asia/Shanghai'):
    # 解析原始时间（带时区）
    dt = datetime.fromisoformat(original_str.replace('Z', '+00:00'))

    # 转换为目标时区（如 UTC+8）
    target_timezone = pytz.timezone(target_tz)
    local_dt = dt.astimezone(target_timezone)

    # 格式化为字符串（截断微秒至 6 位）
    return local_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # 保留 6 位微秒

# 示例输入
original_str = "2025-05-12T5:18:20.666000000+00:00"

formatted_str = convert_time_format(original_str)
# formatted_str = convert_time_with_timezone(original_str)
print(formatted_str)  # 输出: 2025-05-12 15:18:20.439000