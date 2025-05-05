import requests
import json

def test_api():
    """测试API功能是否正常工作"""
    base_url = "http://127.0.0.1:8080"

    # 1. 测试登录
    print("测试登录 API...")
    login_data = {
        "username": "admin",
        "password": "admin"
    }
    login_response = requests.post(
        f"{base_url}/auth/token",
        data={"username": login_data["username"], "password": login_data["password"]}
    )

    if login_response.status_code == 200:
        print("✅ 登录成功")
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 测试获取用户信息
        print("测试获取用户信息 API...")
        user_response = requests.get(f"{base_url}/auth/users/me", headers=headers)
        if user_response.status_code == 200:
            print("✅ 获取用户信息成功")
            print(f"用户信息: {user_response.json()}")
        else:
            print(f"❌ 获取用户信息失败: {user_response.status_code}")
            print(user_response.text)

        # 3. 测试获取表列表
        print("测试获取表列表 API...")
        tables_response = requests.get(f"{base_url}/db/tables", headers=headers)
        if tables_response.status_code == 200:
            tables = tables_response.json()["tables"]
            print("✅ 获取表列表成功")
            print(f"表列表: {tables}")

            if tables:
                # 4. 测试获取表结构
                print(f"测试获取表结构 API (表: {tables[0]})...")
                structure_response = requests.get(f"{base_url}/db/table/{tables[0]}", headers=headers)
                if structure_response.status_code == 200:
                    print("✅ 获取表结构成功")
                    print(f"表结构: {json.dumps(structure_response.json(), indent=2)}")
                else:
                    print(f"❌ 获取表结构失败: {structure_response.status_code}")
                    print(structure_response.text)

                # 5. 测试执行SQL查询
                print("测试执行SQL查询 API...")
                query = f"SELECT * FROM {tables[0]} LIMIT 5"
                query_response = requests.post(
                    f"{base_url}/db/query",
                    headers=headers,
                    json={"query": query}
                )
                if query_response.status_code == 200:
                    print("✅ 执行SQL查询成功")
                    result = query_response.json()
                    print(f"列: {result['columns']}")
                    print(f"行数: {len(result['rows'])}")
                    print(f"首行数据: {json.dumps(result['rows'][0] if result['rows'] else {}, indent=2)}")
                else:
                    print(f"❌ 执行SQL查询失败: {query_response.status_code}")
                    print(query_response.text)

                # 6. 测试非SELECT查询
                print("测试非SELECT查询限制...")
                invalid_query = f"DELETE FROM {tables[0]}"
                invalid_response = requests.post(
                    f"{base_url}/db/query",
                    headers=headers,
                    json={"query": invalid_query}
                )
                if invalid_response.status_code == 403:
                    print("✅ 非SELECT查询被正确禁止")
                else:
                    print(f"❌ 非SELECT查询限制测试失败: {invalid_response.status_code}")
                    print(invalid_response.text)
        else:
            print(f"❌ 获取表列表失败: {tables_response.status_code}")
            print(tables_response.text)
    else:
        print(f"❌ 登录失败: {login_response.status_code}")
        print(login_response.text)

if __name__ == "__main__":
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: 请确保API服务正在运行 (python run.py)")
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}") 