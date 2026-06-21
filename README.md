# Monitoramento de Reservatorios

Sistema de monitoramento de qualidade da agua para reservatorios, integrando um backend Django com um modulo embarcado em ESP32 para coleta, calibracao e acompanhamento operacional.

## O que o projeto faz

- recebe leituras de temperatura, TDS, turbidez e pH;
- autentica cada ESP32 com token por reservatorio;
- processa sinais brutos enviados pelo firmware;
- aplica calibracoes por sensor;
- classifica o status da agua automaticamente;
- exibe dashboard, detalhe, calibracao e relatorio web;
- controla alerta sonoro remoto no ESP32.

## Arquitetura atual

- `1 ESP32 = 1 reservatorio`
- fluxo ativo com `ponto_unico`
- configuracao remota do firmware via `GET /api/esp32/config/`
- ingestao de leituras via `POST /api/esp32/leituras/`
- amostras de calibracao via `POST /api/esp32/calibracao/amostras/`

Fluxo principal:

`ESP32 -> /api/esp32/config/ -> /api/esp32/leituras/ -> app/services/ingestao.py -> app/models.py -> dashboard`

## Stack

- Python 3
- Django 6
- SQLite no ambiente local atual
- ESP32 + biblioteca `MonitoramentoAgua`
- sensores DS18B20, TDS, turbidez e pH

## Estrutura do repositorio

- `app/`: models, views, services, templates e testes
- `setup/`: configuracao do projeto Django
- `MonitoramentoAgua/`: biblioteca e exemplo do firmware ESP32
- `docs/`: documentacao tecnica e operacional
- `manage.py`: entrada do backend Django

## Como rodar o backend

### 1. Criar e ativar um ambiente virtual

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 3. Configurar variaveis de ambiente

Hoje o projeto le oficialmente:

- `DJANGO_SECRET_KEY`

Exemplo no PowerShell:

```powershell
$env:DJANGO_SECRET_KEY="sua-chave-local"
```

Observacao: o fluxo ativo do ESP32 nao depende de token global em `.env`; o token e gerado por reservatorio no proprio Django.

### 4. Aplicar migracoes

```powershell
python manage.py migrate
```

### 5. Criar um usuario

```powershell
python manage.py createsuperuser
```

### 6. Subir o servidor

```powershell
python manage.py runserver 0.0.0.0:8000
```

Depois disso:

- tela de login: `http://127.0.0.1:8000/entrar/`
- admin Django: `http://127.0.0.1:8000/admin/`

## Como usar com o ESP32

1. Crie ou edite um reservatorio no sistema.
2. Copie o `reservatorio_id` e o token de integracao.
3. Grave o firmware de exemplo em `MonitoramentoAgua/examples/esp_reservatorio_unico/`.
4. Conecte-se ao AP do ESP32.
5. Abra o painel local em `http://<ip_do_esp>/<senha_wifi>`.
6. Informe `reservatorio_id`, `ip_django` e token.
7. Salve e acompanhe as leituras no dashboard.

Padroes atuais do firmware:

- IP do AP: `192.168.50.1`
- poll de configuracao: `2s`
- envio normal: `60s`
- envio em calibracao: `5s`

## Testes

Os testes atuais cobrem principalmente:

- autenticacao;
- CRUD e fluxo do reservatorio;
- token do ESP32;
- alerta sonoro;
- relatorios;
- calibracao;
- APIs do ESP32.

Para executar:

```powershell
python manage.py test
```

## Documentacao

- [Visao geral da docs](docs/README.md)
- [Documentacao tecnica](docs/documentacao-tecnica.md)
- [API do ESP32](docs/arquitetura/api-esp32.md)
- [Guia de calibracao](docs/operacao/calibracao.md)
- [Checklist de producao](docs/producao/checklist-producao.md)

## Estado atual

O repositorio esta funcional para uso local e validacao tecnica, mas ainda deve ser tratado como prototipo local avancado. Para producao, ainda faltam endurecimentos como HTTPS, logs, backup, `DEBUG` desligado e estrategia formal de deploy.
