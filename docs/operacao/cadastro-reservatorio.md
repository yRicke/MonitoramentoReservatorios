# Cadastro e Edicao de Reservatorio

## Criacao

O dashboard permite adicionar novos reservatorios. Ao criar, o model:

- gera nome automaticamente se necessario;
- gera token individual do ESP32;
- garante a existencia do `ponto_unico`.

## Campos importantes de edicao

Na tela de edicao o operador pode ajustar:

- nome do reservatorio;
- faixas minimas e maximas de TDS;
- faixas minimas e maximas de turbidez;
- faixa de temperatura;
- faixa de pH;
- intervalo normal de envio do ESP32;
- intervalo de envio durante calibracao.

Tambem pode:

- consultar o `reservatorio_id`;
- copiar o token de integracao;
- regenerar o token do ESP32.

## Regras operacionais

- o status do reservatorio nao e editado manualmente;
- o status e recalculado a partir do ponto monitorado;
- o fluxo ativo usa apenas o ponto canonico unico.

## Acoes de manutencao

Rotas operacionais disponiveis:

- resetar leituras do reservatorio;
- excluir reservatorio;
- regenerar token de integracao do ESP32.
