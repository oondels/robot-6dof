# Feedback de load no gatilho adaptativo do PS5

O controle da garra aplica resistência progressiva no `L2` conforme o load do
servo supera a carga esperada para a velocidade atual. A implementação está em
`src/utils/adaptive_trigger.py` e usa `dualsense-controller` para tratar os
relatórios HID de USB e Bluetooth.

## Preparação no Linux

Instale as dependências Python do projeto e a biblioteca HID do sistema:

```bash
pip install -r requirements.txt
sudo apt install libhidapi-dev
```

Crie `/etc/udev/rules.d/70-dualsense.rules` com:

```text
# USB
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="054c", ATTRS{idProduct}=="0ce6", MODE="0660", GROUP="input"

# Bluetooth
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", KERNELS=="0005:054C:0CE6.*", MODE="0660", GROUP="input"
```

Recarregue as regras e reconecte o controle:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

O usuário que executa o robô deve pertencer ao grupo `input`. Não execute o
controle do robô como `root` apenas para acessar o DualSense.

## Comportamento configurado

```text
gatilho:                         L2
início do load excedente:        40
load excedente para força total: 400
força máxima do gatilho:         200 de 255
força mínima com objeto seguro:  120 de 255
filtro exponencial:              0,25
passo de força:                  8
intervalo mínimo de atualização: 50 ms
```

Depois que o objeto é detectado, o L2 mantém pelo menos `120` de força mesmo
que o operador solte o gatilho ou o load estabilize. Esse estado informa
fisicamente que a garra continua segurando um objeto. O efeito é removido ao
abrir a garra, retornar para home, desabilitar movimento, acionar emergência
ou encerrar o controle. A segurança do robô não depende do feedback do
gatilho: se o HID estiver indisponível, o movimento continua e um aviso é
exibido.

Enquanto o objeto estiver marcado como seguro, uma nova transição do L2 de
solto para pressionado reenvia o efeito HID, mesmo que a força calculada não
tenha mudado. Isso evita perder a resistência depois de soltar e apertar o
gatilho novamente.

A conexão HID é inicializada ao entrar na ação de controle PS5. Isso permite
detectar problemas de biblioteca, permissão ou conexão antes de iniciar o loop
de teleoperação. A resistência permanece desligada até o load excedente atingir
a faixa configurada.
