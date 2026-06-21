# Visao Geral da Arquitetura

## Camadas do sistema

O sistema opera em tres camadas principais:

1. Edge: ESP32, sensores analogicos, buzzer, painel local em AP e cache em NVS.
2. Dominio e ingestao: views Django, services de ingestao e regras de classificacao.
3. Apresentacao: dashboard, detalhe, edicao, calibracao e relatorio.

## Estrutura logica

- `setup/`: configuracao do projeto Django e roteamento principal.
- `app/models.py`: entidades, status, calibracoes e sessoes.
- `app/views.py`: operacao web, contratos do ESP32 e respostas JSON.
- `app/services/ingestao.py`: parse do payload, aplicacao de calibracao e persistencia.
- `MonitoramentoAgua/src/`: biblioteca do ESP32 e painel local.

## Principais decisoes do fluxo atual

- O reservatorio sempre expone um ponto canonico unico.
- O ESP32 consulta configuracao remota a cada 2 segundos.
- Intervalos normal e de calibracao sao definidos por reservatorio no backend.
- O firmware reaplica em RAM e persiste em NVS os ultimos intervalos validos.
- O alerta sonoro e decidido no backend e executado no ESP32.

## Limites assumidos pela arquitetura atual

- Nao ha fluxo operacional confirmado de varios ESP32 por reservatorio.
- Nao ha fluxo operacional atual de ponto antes/depois em payload novo.
- O sistema esta preparado para uso local controlado; producao ainda exige endurecimento adicional.
