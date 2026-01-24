"""
Scheduler Service - 任务调度服务
管理自动刷新任务的执行
"""
from typing import List, Optional, Dict, Callable
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import asyncio
import logging
import pytz

from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models_monitor import MonitorTask, SchedulerJobLog, TaskStatus
from .monitor_delta_calculator import MonitorDeltaCalculator

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """监控任务调度器"""
    
    # 默认调度时间配置 (美东时间)
    DEFAULT_SCHEDULES = {
        'eod_refresh': {
            'hour': 16,
            'minute': 30,
            'description': '收盘后数据刷新'
        },
        'options_refresh': {
            'hour': 18,
            'minute': 0,
            'description': '期权数据刷新'
        },
        'weekend_rebalance': {
            'day_of_week': 'sat',
            'hour': 10,
            'minute': 0,
            'description': '周末重排'
        }
    }
    
    def __init__(self, timezone: str = 'US/Eastern'):
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(timezone))
        self.timezone = pytz.timezone(timezone)
        self._is_running = False
        self._job_callbacks: Dict[str, Callable] = {}
        
        # 添加事件监听
        self.scheduler.add_listener(
            self._on_job_executed, 
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
    
    def start(self):
        """启动调度器"""
        if not self._is_running:
            self.scheduler.start()
            self._is_running = True
            logger.info("Monitor Scheduler started")
    
    def stop(self):
        """停止调度器"""
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Monitor Scheduler stopped")
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    def setup_default_jobs(self):
        """设置默认调度任务"""
        # 收盘后 EOD 数据刷新
        self.add_cron_job(
            job_id='eod_refresh',
            func=self._refresh_all_active_tasks,
            hour=16, minute=30,
            day_of_week='mon-fri',
            description='EOD 数据刷新'
        )
        
        # 期权数据刷新
        self.add_cron_job(
            job_id='options_refresh',
            func=self._refresh_options_data,
            hour=18, minute=0,
            day_of_week='mon-fri',
            description='期权数据刷新'
        )
        
        # 周末重新计算评分
        self.add_cron_job(
            job_id='weekend_rebalance',
            func=self._weekend_rebalance,
            hour=10, minute=0,
            day_of_week='sat',
            description='周末评分重算'
        )
        
        logger.info("Default scheduler jobs configured")
    
    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        hour: int,
        minute: int = 0,
        day_of_week: str = 'mon-fri',
        description: str = ''
    ):
        """添加 Cron 任务"""
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                timezone=self.timezone
            ),
            id=job_id,
            name=description,
            replace_existing=True
        )
        logger.info(f"Added cron job: {job_id} at {hour}:{minute:02d} ({day_of_week})")
    
    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        minutes: int = 60,
        description: str = ''
    ):
        """添加间隔任务"""
        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            name=description,
            replace_existing=True
        )
        logger.info(f"Added interval job: {job_id} every {minutes} minutes")
    
    def remove_job(self, job_id: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.warning(f"Failed to remove job {job_id}: {e}")
    
    def get_jobs(self) -> List[Dict]:
        """获取所有任务"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs
    
    async def trigger_job(self, job_id: str):
        """立即触发任务"""
        job = self.scheduler.get_job(job_id)
        if job:
            await job.func()
            logger.info(f"Manually triggered job: {job_id}")
        else:
            raise ValueError(f"Job {job_id} not found")
    
    def _on_job_executed(self, event):
        """任务执行回调"""
        job_id = event.job_id
        if event.exception:
            logger.error(f"Job {job_id} failed: {event.exception}")
            self._log_job_execution(job_id, 'failed', str(event.exception))
        else:
            logger.info(f"Job {job_id} executed successfully")
            self._log_job_execution(job_id, 'success')
    
    def _log_job_execution(
        self, 
        job_id: str, 
        status: str, 
        error_message: Optional[str] = None
    ):
        """记录任务执行日志"""
        db = SessionLocal()
        try:
            job = self.scheduler.get_job(job_id)
            log = SchedulerJobLog(
                job_id=job_id,
                job_name=job.name if job else job_id,
                started_at=datetime.now(self.timezone),
                completed_at=datetime.now(self.timezone),
                status=status,
                error_message=error_message
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log job execution: {e}")
        finally:
            db.close()
    
    # ==================== 任务执行函数 ====================
    
    async def _refresh_all_active_tasks(self):
        """刷新所有激活的任务"""
        db = SessionLocal()
        try:
            tasks = db.query(MonitorTask).filter(
                MonitorTask.status == TaskStatus.ACTIVE.value,
                MonitorTask.is_auto_refresh == True
            ).all()
            
            logger.info(f"Starting EOD refresh for {len(tasks)} active tasks")
            
            calculator = MonitorDeltaCalculator(db)
            
            for task in tasks:
                try:
                    result = calculator.calculate_and_save_scores(task.id)
                    logger.info(f"Task {task.id} refreshed: {result['success_count']} ETFs updated")
                except Exception as e:
                    logger.error(f"Failed to refresh task {task.id}: {e}")
            
        finally:
            db.close()
    
    async def _refresh_options_data(self):
        """刷新期权数据（需要实现与 IBKR/Futu 的集成）"""
        logger.info("Options data refresh - placeholder")
        # TODO: 实现期权数据刷新
        # 这里需要调用 IBKR 或 Futu 服务获取期权数据
        pass
    
    async def _weekend_rebalance(self):
        """周末重新计算所有评分"""
        db = SessionLocal()
        try:
            tasks = db.query(MonitorTask).filter(
                MonitorTask.status == TaskStatus.ACTIVE.value
            ).all()
            
            logger.info(f"Starting weekend rebalance for {len(tasks)} tasks")
            
            calculator = MonitorDeltaCalculator(db)
            
            for task in tasks:
                try:
                    # 重新计算 Delta
                    updated = calculator.recalculate_all_deltas(task.id)
                    logger.info(f"Task {task.id} rebalanced: {updated} snapshots updated")
                except Exception as e:
                    logger.error(f"Failed to rebalance task {task.id}: {e}")
            
        finally:
            db.close()


# 全局调度器实例
_scheduler_instance: Optional[MonitorScheduler] = None


def get_scheduler() -> MonitorScheduler:
    """获取调度器实例（单例）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MonitorScheduler()
    return _scheduler_instance


def init_scheduler(auto_start: bool = True) -> MonitorScheduler:
    """初始化调度器"""
    scheduler = get_scheduler()
    scheduler.setup_default_jobs()
    if auto_start:
        scheduler.start()
    return scheduler


# ==================== API 路由所需的函数 ====================

async def trigger_task_refresh(task_id: int, db: Session):
    """手动触发任务刷新"""
    task = db.query(MonitorTask).filter(MonitorTask.id == task_id).first()
    if not task:
        raise ValueError(f"Task {task_id} not found")
    
    calculator = MonitorDeltaCalculator(db)
    result = calculator.calculate_and_save_scores(task_id)
    
    logger.info(f"Manual refresh for task {task_id}: {result['success_count']} ETFs updated")
    return result
