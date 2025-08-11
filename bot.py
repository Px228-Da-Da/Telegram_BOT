# bot.py (обновленная версия)
import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, EXPIRE_SCAN_INTERVAL
from db import init_db
from handlers import common, pm, exec
# Новые импорты
from scheduler import scheduler, check_expired_tasks, schedule_existing_tasks

async def main():
    init_db()

    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(pm.router)
    dp.include_router(exec.router)

    # Запускаем фоновую задачу для проверки просрочек
    scheduler.add_job(check_expired_tasks, "interval", seconds=EXPIRE_SCAN_INTERVAL, args=[bot])
    
    # При старте восстанавливаем напоминания для активных задач
    schedule_existing_tasks(bot)
    
    # Запускаем планировщик
    scheduler.start()

    print("Бот запущен...")
    # Передаем экземпляр бота в хэндлеры для дальнейшего использования
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
        if scheduler.running:
            scheduler.shutdown()