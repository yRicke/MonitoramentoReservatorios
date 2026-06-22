# Modelo de Dados

## `Reservatorio`

Representa a unidade principal de operacao do sistema.

Campos e responsabilidades relevantes:

- nome e usuario dono;
- status geral do reservatorio;
- faixas minimas e maximas de TDS, turbidez, temperatura e pH;
- metas antigas mantidas por compatibilidade;
- intervalo de envio normal do ESP32;
- intervalo de envio em calibracao;
- controle de alerta sonoro: silenciado, silenciado permanente e teste em andamento.

## `PontoMonitoramento`

Representa o ponto usado para registrar leituras e calibracoes.

Estado atual:

- tipo canonico: `ponto_unico`
- aliases historicos: `antes_tratamento` e `depois_tratamento`
- os aliases antigos sao mapeados internamente para `ponto_unico`

Tambem concentra:

- status atual do ponto;
- parametros de calibracao de temperatura;
- parametros de calibracao de pH;
- parametros de calibracao de TDS;
- parametros de calibracao de turbidez.

## `LeituraQualidade`

Armazena o historico de medicoes processadas.

Campos principais:

- `temperatura`
- `tds`
- `turbidez`
- `ph`
- `sinais_brutos`
- `status_leitura`
- `status_origem`
- `confianca`
- `modelo_versao`
- `data_hora`

## `SessaoCalibracao`

Controla a janela ativa de calibracao.

Campos principais:

- `sensor`
- `status`
- `iniciada_por`
- `intervalo_envio_ms`
- `qtd_amostras`
- `atraso_amostra_ms`
- `dados_fluxo`
- `iniciada_em`
- `ultima_amostra_em`
- `encerrada_em`
- `expira_em`

No fluxo da UI atual, a sessao e aberta com TTL de 10 minutos, embora o model tenha padroes genericos mais amplos.

## `AmostraCalibracao`

Guarda as amostras recebidas do firmware durante a sessao ativa.

Campos principais:

- `temperatura`
- `adc_tds`
- `adc_turb`
- `adc_ph`
- `firmware_ts_ms`
- `sinais_brutos`
- `coletada_em`

## Relacoes

- `Reservatorio` possui varios `PontoMonitoramento`, mas o fluxo ativo usa apenas o ponto canonico.
- `PontoMonitoramento` possui varias `LeituraQualidade`.
- `PontoMonitoramento` possui varias `SessaoCalibracao`.
- `SessaoCalibracao` possui varias `AmostraCalibracao`.
