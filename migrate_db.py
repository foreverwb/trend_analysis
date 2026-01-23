#!/usr/bin/env python3
"""
数据库迁移脚本
用于添加 SymbolPool 表的新字段
"""
import sqlite3
import os

def migrate():
    db_path = "backend/trend_analysis.db"
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        print("将在首次运行时自动创建")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查并添加新字段
    new_columns = [
        ("sma50", "REAL"),
        ("sma200", "REAL"),
        ("rsi", "REAL"),
        ("positioning_score", "REAL"),
        ("term_score", "REAL"),
        ("iv30", "REAL"),
        ("iv60", "REAL"),
        ("iv90", "REAL"),
        ("iv_slope", "REAL"),
    ]
    
    # 获取当前表结构
    cursor.execute("PRAGMA table_info(symbol_pool)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE symbol_pool ADD COLUMN {col_name} {col_type}")
                print(f"✓ 添加字段: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ 添加字段失败 {col_name}: {e}")
        else:
            print(f"- 字段已存在: {col_name}")
    
    conn.commit()
    conn.close()
    print("\n迁移完成!")

if __name__ == "__main__":
    migrate()
