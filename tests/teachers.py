import asyncio
import aiohttp

teachers = [
    {"username": "@teacher1", "telegram_id": 1000001, "phone_number": "9120000001", "first_name": "Алексей", "last_name": "Иванов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher2", "telegram_id": 1000002, "phone_number": "9120000002", "first_name": "Мария", "last_name": "Петрова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher3", "telegram_id": 1000003, "phone_number": "9120000003", "first_name": "Игорь", "last_name": "Сидоров", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher4", "telegram_id": 1000004, "phone_number": "9120000004", "first_name": "Ольга", "last_name": "Кузнецова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher5", "telegram_id": 1000005, "phone_number": "9120000005", "first_name": "Дмитрий", "last_name": "Смирнов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher6", "telegram_id": 1000006, "phone_number": "9120000006", "first_name": "Екатерина", "last_name": "Попова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher7", "telegram_id": 1000007, "phone_number": "9120000007", "first_name": "Никита", "last_name": "Лебедев", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher8", "telegram_id": 1000008, "phone_number": "9120000008", "first_name": "Светлана", "last_name": "Новикова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher9", "telegram_id": 1000009, "phone_number": "9120000009", "first_name": "Павел", "last_name": "Морозов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher10", "telegram_id": 1000010, "phone_number": "9120000010", "first_name": "Анна", "last_name": "Фролова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher11", "telegram_id": 1000011, "phone_number": "9120000011", "first_name": "Роман", "last_name": "Богданов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher12", "telegram_id": 1000012, "phone_number": "9120000012", "first_name": "Ирина", "last_name": "Волкова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher13", "telegram_id": 1000013, "phone_number": "9120000013", "first_name": "Владимир", "last_name": "Макаров", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher14", "telegram_id": 1000014, "phone_number": "9120000014", "first_name": "Наталья", "last_name": "Алексеева", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher15", "telegram_id": 1000015, "phone_number": "9120000015", "first_name": "Сергей", "last_name": "Захаров", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher16", "telegram_id": 1000016, "phone_number": "9120000016", "first_name": "Елена", "last_name": "Крылова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher17", "telegram_id": 1000017, "phone_number": "9120000017", "first_name": "Юрий", "last_name": "Панов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher18", "telegram_id": 1000018, "phone_number": "9120000018", "first_name": "Оксана", "last_name": "Михайлова", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher19", "telegram_id": 1000019, "phone_number": "9120000019", "first_name": "Максим", "last_name": "Титов", "role": "teacher", "password": "Test1234"},
    {"username": "@teacher20", "telegram_id": 1000020, "phone_number": "9120000020", "first_name": "Людмила", "last_name": "Соловьёва", "role": "teacher", "password": "Test1234"}
]

API_URL = "https://api.tsu-consult.orexi4.ru/auth/register/"

async def register_teacher(session, teacher):
    try:
        async with session.post(API_URL, json=teacher) as response:
            text = await response.text()
            if response.status < 300:
                data = await response.json()
                print(f"✅ Успешно зарегистрирован: {teacher['username']}")
                print(f"   Access token: {data.get('access')}")
                return data
            else:
                print(f"❌ Ошибка при регистрации {teacher['username']}: {response.status} - {text}")
    except Exception as e:
        print(f"❌ Исключение для {teacher['username']}: {e}")


async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [register_teacher(session, t) for t in teachers]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
