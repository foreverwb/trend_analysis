#!/usr/bin/env python3
"""
数据库迁移脚本 - 覆盖范围功能优化

功能：将 coverage_type 单值字段迁移为 coverage_types JSON 数组字段

使用方法：
    python migrate_coverage_types.py

注意事项：
    1. 执行前请备份数据库
    2. 确保已安装所需依赖
    3. 检查数据库连接配置
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil

# ============================================================
# 配置
# ============================================================

# 数据库路径（根据实际项目调整）
DATABASE_PATH = "backend/trend_analysis.db"

# 备份目录
BACKUP_DIR = "backups"

# ============================================================
# 迁移逻辑
# ============================================================

def backup_database(db_path: str) -> str:
    """备份数据库文件"""
    backup_dir = Path(BACKUP_DIR)
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"monitor_backup_{timestamp}.db"
    
    shutil.copy(db_path, backup_path)
    
    print(f"✅ 数据库已备份到: {backup_path}")
    return str(backup_path)


def check_migration_needed(conn: sqlite3.Connection) -> bool:
    """检查是否需要迁移"""
    cursor = conn.cursor()
    
    # 检查表结构
    cursor.execute("PRAGMA table_info(monitor_tasks)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    if 'coverage_types' in columns:
        print("ℹ️  字段 coverage_types 已存在，跳过迁移")
        return False
    
    if 'coverage_type' not in columns:
        print("⚠️  字段 coverage_type 不存在，可能是新数据库")
        return False
    
    return True


def migrate_coverage_types(conn: sqlite3.Connection) -> int:
    """执行迁移"""
    cursor = conn.cursor()
    
    # Step 1: 添加新字段
    print("📝 Step 1: 添加 coverage_types 字段...")
    cursor.execute("""
        ALTER TABLE monitor_tasks 
        ADD COLUMN coverage_types TEXT DEFAULT '["top15"]'
    """)
    
    # Step 2: 迁移数据
    print("📝 Step 2: 迁移现有数据...")
    cursor.execute("""
        SELECT id, coverage_type FROM monitor_tasks 
        WHERE coverage_type IS NOT NULL AND coverage_type != ''
    """)
    tasks = cursor.fetchall()
    
    migrated_count = 0
    for task_id, coverage_type in tasks:
        # 将单值转换为数组
        coverage_types = json.dumps([coverage_type])
        cursor.execute("""
            UPDATE monitor_tasks 
            SET coverage_types = ? 
            WHERE id = ?
        """, (coverage_types, task_id))
        migrated_count += 1
    
    # Step 3: 处理空值
    print("📝 Step 3: 处理空值...")
    cursor.execute("""
        UPDATE monitor_tasks 
        SET coverage_types = '[]' 
        WHERE coverage_types IS NULL OR coverage_types = ''
    """)
    
    conn.commit()
    return migrated_count


def verify_migration(conn: sqlite3.Connection) -> bool:
    """验证迁移结果"""
    cursor = conn.cursor()
    
    # 检查新字段存在
    cursor.execute("PRAGMA table_info(monitor_tasks)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    if 'coverage_types' not in columns:
        print("❌ 验证失败：coverage_types 字段不存在")
        return False
    
    # 检查数据格式
    cursor.execute("SELECT id, coverage_types FROM monitor_tasks")
    for task_id, coverage_types in cursor.fetchall():
        try:
            data = json.loads(coverage_types)
            if not isinstance(data, list):
                print(f"❌ 验证失败：任务 {task_id} 的 coverage_types 不是数组")
                return False
        except json.JSONDecodeError:
            print(f"❌ 验证失败：任务 {task_id} 的 coverage_types 不是有效 JSON")
            return False
    
    print("✅ 迁移验证通过")
    return True


def print_migration_summary(conn: sqlite3.Connection):
    """打印迁移摘要"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM monitor_tasks")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT coverage_types, COUNT(*) as cnt 
        FROM monitor_tasks 
        GROUP BY coverage_types
    """)
    distribution = cursor.fetchall()
    
    print("\n" + "=" * 50)
    print("📊 迁移摘要")
    print("=" * 50)
    print(f"总任务数: {total_count}")
    print("\n覆盖范围分布:")
    for coverage_types, count in distribution:
        print(f"  {coverage_types}: {count} 条")
    print("=" * 50 + "\n")


def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("🚀 覆盖范围字段迁移工具")
    print("=" * 50 + "\n")
    
    db_path = Path(DATABASE_PATH)
    
    # 检查数据库文件
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        print("请检查 DATABASE_PATH 配置")
        return
    
    # 备份数据库
    print("📦 正在备份数据库...")
    backup_path = backup_database(str(db_path))
    
    # 连接数据库
    conn = sqlite3.connect(str(db_path))
    
    try:
        # 检查是否需要迁移
        if not check_migration_needed(conn):
            conn.close()
            return
        
        # 执行迁移
        print("\n🔄 开始迁移...")
        migrated_count = migrate_coverage_types(conn)
        print(f"✅ 迁移完成，共迁移 {migrated_count} 条记录")
        
        # 验证迁移
        print("\n🔍 验证迁移结果...")
        if not verify_migration(conn):
            print("\n⚠️  迁移验证失败，请检查数据")
            print(f"📂 可从备份恢复: {backup_path}")
            return
        
        # 打印摘要
        print_migration_summary(conn)
        
        print("🎉 迁移成功完成！")
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        print(f"📂 请从备份恢复: {backup_path}")
        conn.rollback()
        raise
    
    finally:
        conn.close()


# ============================================================
# 回滚脚本
# ============================================================

def rollback_migration(backup_path: str):
    """从备份回滚迁移"""
    db_path = Path(DATABASE_PATH)
    backup = Path(backup_path)
    
    if not backup.exists():
        print(f"❌ 备份文件不存在: {backup_path}")
        return
    
    # 恢复备份
    shutil.copy(backup, db_path)
    print(f"✅ 已从备份恢复: {backup_path}")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        if len(sys.argv) < 3:
            print("用法: python migrate_coverage_types.py --rollback <backup_path>")
            sys.exit(1)
        rollback_migration(sys.argv[2])
    else:
        main()
