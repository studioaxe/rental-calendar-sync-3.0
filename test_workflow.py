import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Ler variáveis
owner = os.getenv('GITHUB_OWNER')
repo = os.getenv('GITHUB_REPO')
workflow = os.getenv('GITHUB_WORKFLOW')
token = os.getenv('GITHUB_TOKEN')
branch = os.getenv('GITHUB_BRANCH', 'main')

print("=" * 60)
print("TESTE DE DISPARO DE WORKFLOW")
print("=" * 60)
print(f"Owner:    {owner}")
print(f"Repo:     {repo}")
print(f"Workflow: {workflow}")
print(f"Branch:   {branch}")
print(f"Token:    {token[:20]}..." if token else "Token: MISSING!")
print("=" * 60)

# Construir URL da API
url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}
payload = {
    "ref": branch
}

print(f"\nURL: {url}")
print(f"Method: POST")
print(f"Payload: {payload}")
print("\nA tentar disparar workflow...")

try:
    response = requests.post(url, json=payload, headers=headers)
    
    print(f"\n✓ Response Status: {response.status_code}")
    print(f"✓ Response Headers: {dict(response.headers)}")
    
    if response.text:
        print(f"✓ Response Body: {response.text}")
    
    if response.status_code == 204:
        print("\n✅ SUCESSO! Workflow foi disparado!")
    else:
        print(f"\n❌ ERRO! Status {response.status_code}")
        print(f"Mensagem: {response.text}")
        
except Exception as e:
    print(f"\n❌ ERRO NA REQUISIÇÃO: {str(e)}")
