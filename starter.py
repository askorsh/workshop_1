"""
Описание запроса создания горячего кофе (POST).

HTTP-метод: POST
URL: https://pycourse-2026.duckdns.org/coffee/hot/
Заголовки:
    Content-Type: application/json

JSON-тело (все поля обязательны — проверено запросами):
    - title:       str,   непустая строка, название напитка
    - description: str,   описание напитка
    - ingredients: list[str], список ингредиентов
    - image:       str,   URL изображения (может быть пустой строкой)

Поле id клиент НЕ отправляет — его генерирует сервер.
Известные ограничения (подтверждены реальными запросами):
    - без поля image сервер отвечает 400 Bad Request
    - неверный Content-Type также приведёт к ошибке
    - 404 на несуществующий ресурс возвращает {} (пустой JSON)

Что задаёт клиент: title, description, ingredients, image.
Что задаёт сервер: id, а также заголовок Location: /coffee/hot/<id>.

Ожидаемый успешный статус: 201 Created
Форма ответа: JSON-объект вида
    {"title": "...", "description": "...", "ingredients": [...], "image": "...", "id": 59}

Правила, проверенные только в клиенте (не сервером):
    - непустота title,
    - непустой список ingredients.
"""
from __future__ import annotations
import requests
from uuid import uuid4


JsonObject = dict[str, object]


class CoffeeApiError(Exception):
    pass


class CoffeeNotFoundError(CoffeeApiError):
    pass


class SampleApisCoffeeClient:
    def __init__(
        self,
        base_url: str = "https://pycourse-2026.duckdns.org/coffee/hot/",
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def list_drinks(self) -> list[JsonObject]:
        return self._request("GET").json()

    def get_drink(self, drink_id: int) -> JsonObject:
        return self._request("GET", f"/{drink_id}/").json()

    def create_drink(self, payload: JsonObject) -> JsonObject:
        return self._request("POST", payload=payload).json()

    def replace_drink(
        self,
        drink_id: int,
        payload: JsonObject,
    ) -> JsonObject:
        return self._request("PUT", f"/{drink_id}/", payload=payload).json()

    def update_drink(
        self,
        drink_id: int,
        changes: JsonObject,
    ) -> JsonObject:
        return self._request("PATCH", f"/{drink_id}/", payload=changes).json()

    def delete_drink(self, drink_id: int) -> None:
        self._request("DELETE", f"/{drink_id}/")

    def _request(
        self,
        method: str,
        path: str = "",
        payload: JsonObject | None = None,
    ) -> requests.Response:
        url = f"{self._base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                json=payload,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as error:
            raise CoffeeApiError(f"Сетевая ошибка: {error}") from error

        if response.status_code == 404:
            raise CoffeeNotFoundError(f"Ресурс не найден: {url}")

        if not response.ok:
            raise CoffeeApiError(
                f"HTTP {response.status_code}: {response.text[:200]}"
            )

        # Тело есть у всех успешных ответов этого API (даже DELETE и 404 → {}),
        # но проверку Content-Type делаем всегда — требование задания.
        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            raise CoffeeApiError(
                f"Ожидался JSON, получен Content-Type: {content_type}"
            )

        return response


def main() -> int:
    client = SampleApisCoffeeClient()
    marker = uuid4().hex[:8]
    created_id: int | None = None

    try:
        print("=" * 60)
        print(f"Метка группы: {marker}")
        print("=" * 60)

        # 1. GET коллекции
        print("\n[1] GET коллекции /coffee/hot/")
        drinks = client.list_drinks()
        print(f"    OK: получено напитков: {len(drinks)}")

        # 2. POST — создать с меткой
        print("\n[2] POST — создание напитка с меткой")
        payload: JsonObject = {
            "title": f"Coffee-{marker}",
            "description": "Лабораторный напиток",
            "ingredients": ["water", "coffee"],
            "image": "https://example.com/coffee.jpg",
        }
        created = client.create_drink(payload)
        created_id = int(created["id"])
        print(f"    OK: создан id={created_id}")

        # 3. GET по id — проверить, что сохранилось
        print(f"\n[3] GET /coffee/hot/{created_id}/")
        fetched = client.get_drink(created_id)
        assert fetched["title"] == payload["title"]
        assert fetched["description"] == payload["description"]
        assert fetched["ingredients"] == payload["ingredients"]
        assert fetched["image"] == payload["image"]
        print("    OK: поля совпадают с отправленными")

        # 4. PUT — полная замена
        print(f"\n[4] PUT /coffee/hot/{created_id}/ — полная замена")
        replaced_payload: JsonObject = {
            "title": f"Coffee-{marker}-v2",
            "description": "Заменено целиком",
            "ingredients": ["milk", "coffee"],
            "image": "https://example.com/new.jpg",
        }
        replaced = client.replace_drink(created_id, replaced_payload)
        assert replaced["title"] == replaced_payload["title"]
        assert replaced["description"] == replaced_payload["description"]
        assert replaced["ingredients"] == replaced_payload["ingredients"]
        assert replaced["image"] == replaced_payload["image"]
        print("    OK: все поля заменены")

        # 5. PATCH — частичное изменение
        print(f"\n[5] PATCH /coffee/hot/{created_id}/ — меняем только description")
        patched = client.update_drink(created_id, {"description": "патчено"})
        assert patched["description"] == "патчено"
        assert patched["title"] == replaced_payload["title"]
        assert patched["ingredients"] == replaced_payload["ingredients"]
        print("    OK: изменено только description, остальное сохранено")

        # 6. GET — повторная проверка
        print(f"\n[6] GET /coffee/hot/{created_id}/ — повторная проверка")
        after = client.get_drink(created_id)
        assert after["description"] == "патчено"
        assert after["title"] == replaced_payload["title"]
        print("    OK: изменения подтверждены сервером")

        # 7. DELETE
        print(f"\n[7] DELETE /coffee/hot/{created_id}/")
        client.delete_drink(created_id)
        print("    OK: сервер подтвердил удаление")

        # 8. GET — ожидаем 404
        print(f"\n[8] GET /coffee/hot/{created_id}/ — ожидаем 404")
        try:
            client.get_drink(created_id)
        except CoffeeNotFoundError:
            print("    OK: получен 404, ресурс действительно удалён")
            created_id = None
        else:
            print("    ОШИБКА: ресурс всё ещё доступен")
            return 1

        print("\n" + "=" * 60)
        print("Сценарий завершён успешно")
        print("=" * 60)
    except (CoffeeApiError, ValueError) as error:
        print(f"\nОшибка: {error}. Метка группы: {marker}")
        return 1
    finally:
        if created_id is not None:
            print(f"\n[finally] Попытка удалить id={created_id}")
            try:
                client.delete_drink(created_id)
                print("    OK: очищено")
            except CoffeeNotFoundError:
                print("    Уже удалено")
            except CoffeeApiError as error:
                print(f"    Не удалось удалить id={created_id}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
