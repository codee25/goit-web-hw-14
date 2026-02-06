def test_signup(client):
    response = client.post(
        "/signup",
        json={
            "username": "tester", 
            "email": "tester@test.com", 
            "password": "pass123"  # 7 символів — підходить під ліміт 6-10
        }
    )
    assert response.status_code == 201