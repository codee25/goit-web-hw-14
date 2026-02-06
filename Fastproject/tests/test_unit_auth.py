import pickle
import unittest
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.orm import Session

import models
from auth import auth_service, get_current_user


class TestAuth(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Створюємо фейкову сесію БД та Redis
        self.session = MagicMock(spec=Session)
        self.user = models.User(id=1, email="test@example.com")
        # Мокаємо Redis у класі Auth
        auth_service.r = AsyncMock()

    async def test_get_current_user_cached(self):
        # Налаштовуємо Redis на повернення закешованого юзера
        auth_service.r.get.return_value = pickle.dumps(self.user)
        
        # Імітуємо токен
        token = MagicMock()
        token.credentials = "fake_token"
        
        # Мокаємо декодування токена
        with unittest.mock.patch("jose.jwt.decode", return_value={"sub": "test@example.com"}):
            result = await get_current_user(token=token, db=self.session)
            self.assertEqual(result.email, self.user.email)
            # Переконуємось, що запит до БД НЕ виконувався (дані з кешу)
            self.session.query.assert_not_called()

    async def test_get_current_user_database(self):
        # Redis порожній, дані тягнуться з БД
        auth_service.r.get.return_value = None
        self.session.query().filter().first.return_value = self.user
        
        token = MagicMock(credentials="fake_token")
        with unittest.mock.patch("jose.jwt.decode", return_value={"sub": "test@example.com"}):
            result = await get_current_user(token=token, db=self.session)
            self.assertEqual(result.email, self.user.email)