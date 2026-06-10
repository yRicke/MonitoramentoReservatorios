# Guia de Operacao do Sistema

## 1. Objetivo
Este guia resume a operacao do ambiente completo:
- ESP32 em campo;
- backend Django;
- interface web.

## 2. Pre-requisitos
Backend:
- ambiente Python do projeto configurado;
- banco inicializado;
- servidor Django acessivel no IP definido para o ESP32.

Edge:
- firmware generico gravado no ESP32;
- acesso ao AP do dispositivo;
- token do reservatorio gerado no sistema.

## 3. Fluxo Basico
1. Acessar `/entrar/`.
2. Abrir a edicao do reservatorio.
3. Copiar `reservatorio_id` e token do ESP32.
4. Acessar o painel local do ESP32.
5. Salvar a configuracao do dispositivo.
6. Voltar ao dashboard e acompanhar as leituras.

## 4. Rotina Diaria
1. Verificar reservatorios sem dados recentes.
2. Conferir status geral dos cards.
3. Abrir detalhes dos casos em alerta.
4. Revisar historico das metricas.
5. Acionar calibracao quando necessario.

## 5. Dashboard e Detalhe
Dashboard:
- visao consolidada dos reservatorios;
- medias por periodo;
- filtro por nome.

Detalhe do reservatorio:
- status atual;
- estado do alerta sonoro;
- ultimas medicoes;
- graficos historicos;
- acesso para editar e calibrar.

Quando o status entrar em `perigo`, a tela de detalhe permite silenciar ou reativar o alerta sonoro.
O detalhe tambem oferece um botao de silenciamento permanente, que bloqueia a buzina ate reativacao manual.

## 6. Edicao do Reservatorio
Na tela de edicao:
- revisar faixas de referencia;
- consultar `reservatorio_id`;
- copiar o token de integracao;
- ajustar `intervalo de envio normal`;
- ajustar `intervalo de envio em calibracao`;
- regenerar token quando necessario.

## 7. Incidentes Comuns
### Sem dados no dashboard
1. confirmar backend online;
2. validar `ip_django` no painel do ESP32;
3. validar token atual do reservatorio;
4. verificar se o notebook esta conectado ao AP do ESP32.

### Erro 401 nos endpoints do ESP32
1. conferir se o token foi regenerado no sistema;
2. atualizar o painel local do ESP32 com o novo token.

### Erro 400 na API
1. validar `reservatorio_id`;
2. conferir campos obrigatorios do payload;
3. garantir que o fluxo ativo nao envie `ponto_tipo`.
