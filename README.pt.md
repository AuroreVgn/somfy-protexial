# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Sobre

Esta integração permite que o Home Assistant comunique com uma central de alarme Somfy Protexial, Protexiom ou Protexial IO.

### Modelos testados

| Modelo | Versão | Estado |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

Esta lista não é exaustiva. A integração também pode funcionar com outras versões de centrais Somfy.

### Funcionalidades suportadas

- Controlo do alarme através das zonas A, B e C
- Controlo de estores
- Controlo de luzes
- Leitura do estado geral da central
- Leitura de falhas e estados dos dispositivos Somfy

### Entidades principais

| Entidade | Descrição |
|---|---|
| `alarm_control_panel` | Modos `armed_away`, `armed_home`, `armed_night` e desarmado |
| `cover` | Abrir, fechar e parar os estores, sem controlo de posição |
| `light` | Ligar e desligar as luzes |
| `binary_sensor` | Bateria, movimento, abertura, sabotagem, rádio, GSM, câmara e estados agregados dos dispositivos |
| `sensor` | Operador GSM, qualidade do sinal GSM e última sincronização |
| `button` | Reposição de falhas de bateria, alarme e ligação rádio |

## Instalação

### Opção A — Instalação através do HACS (recomendada)

1. Abra **Integrações** no HACS.
2. Abra o menu **⋮** e depois **Repositórios personalizados**.
3. Adicione `https://github.com/AuroreVgn/somfy-protexial`.
4. Selecione a categoria **Integração**.
5. Procure **Somfy Protexial** e descarregue a integração.
6. Reinicie o Home Assistant.

### Opção B — Instalação manual

1. Descarregue o arquivo da versão mais recente disponível.
2. Localize a pasta que contém `configuration.yaml`.
3. Crie `custom_components` se ainda não existir.
4. Crie `custom_components/somfy_protexial`.
5. Extraia os ficheiros da integração para essa pasta.
6. Reinicie o Home Assistant.

## Configuração

No Home Assistant, abra:

**Definições → Dispositivos e serviços → Adicionar integração → Somfy Protexial**

### 1. Endereço da central

Introduza o URL local da interface web da central, por exemplo:

```text
http://192.168.1.234
```

Inclua a porta no URL se a central utilizar uma porta diferente.

### 2. Autenticação

Consoante a geração da central, o assistente pode solicitar:

- a palavra-passe da conta de utilizador;
- o código correspondente ao desafio do cartão de autenticação;
- em algumas Protexiom mais antigas, uma etapa de administrador seguida da palavra-passe do utilizador.

### 3. Configuração adicional

Os modos de ativação utilizam as zonas configuradas na central Somfy:

- **Ausente**: zonas A + B + C;
- **Noite**: combinação opcional de zonas;
- **Em casa**: combinação opcional de zonas.

Pode ser definido um código de ativação. Esse código será pedido ao ativar ou desativar o alarme.

O intervalo de atualização pode ser definido entre 15 segundos e 1 hora. O valor predefinido é 60 segundos.

## Informações importantes

### Compatibilidade

A lista de modelos testados não é exaustiva. Pode comunicar o funcionamento com outra versão nas issues do repositório ou no [tópico de discussão HACF](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589).

O ano da interface aparece geralmente no fundo das páginas da central. Algumas centrais também disponibilizam a versão em:

```text
http://ENDERECO_DA_CENTRAL/cfg/vers
```

### Utilização da interface web original da Somfy

A central suporta geralmente apenas uma sessão de utilizador de cada vez. Desative ou recarregue temporariamente a integração antes de utilizar a interface web original se a ligação for recusada.

### Reconfiguração

A integração pode ser reconfigurada através da interface do Home Assistant.

## Contribuições

Contribuições, relatórios de erros e comentários de compatibilidade são bem-vindos. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) antes de propor alterações.

## Créditos

O código inicial baseia-se parcialmente no modelo `integration_blueprint` de Ludeeus.

## Licença

Este projeto é distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
