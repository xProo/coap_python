import asyncio
import random
import time
import aiocoap
import aiocoap.resource as resource


# ---------------------------------------------------------
# Ressource observable : la température change toute seule
# ---------------------------------------------------------
class TemperatureResource(resource.ObservableResource):
    """Simule un capteur de température : la valeur change
    toutes les 2 secondes, et tous les clients en mode
    OBSERVE reçoivent une notification."""

    ct = 0  # text/plain, publié dans /.well-known/core

    def __init__(self):
        super().__init__()
        self.value = 22.5
        self.notify = True   # on avertit même si la valeur ne change pas

    async def render_get(self, request):
        return aiocoap.Message(
            code=aiocoap.Code.CONTENT,
            payload=str(self.value).encode()
        )

    async def render_put(self, request):
        """Permet de fixer manuellement la température."""
        try:
            self.value = float(request.payload.decode())
        except ValueError:
            return aiocoap.Message(code=aiocoap.Code.BAD_REQUEST)
        self.updated_state()   # prévenir les observateurs
        return aiocoap.Message(code=aiocoap.Code.CHANGED)

    async def background_task(self):
        """Change la valeur périodiquement tant que le serveur tourne."""
        while True:
            await asyncio.sleep(2)
            self.value = round(20 + random.random() * 5, 1)  # entre 20.0 et 25.0
            self.updated_state()   # envoie une notification aux observateurs


# ---------------------------------------------------------
# LED : on/off, ressource simple (lecture/écriture)
# ---------------------------------------------------------
class LedResource(resource.Resource):
    ct = 0

    def __init__(self):
        super().__init__()
        self.etat = "off"

    async def render_get(self, request):
        return aiocoap.Message(code=aiocoap.Code.CONTENT,
                               payload=self.etat.encode())

    async def render_put(self, request):
        nouvel_etat = request.payload.decode().strip().lower()
        if nouvel_etat not in ("on", "off"):
            return aiocoap.Message(code=aiocoap.Code.BAD_REQUEST,
                                   payload=b"use 'on' ou 'off'")
        self.etat = nouvel_etat
        return aiocoap.Message(code=aiocoap.Code.CHANGED)


# ---------------------------------------------------------
# Journal : POST ajoute une entrée, GET les liste
# ---------------------------------------------------------
class LogsResource(resource.Resource):
    ct = 0

    def __init__(self):
        super().__init__()
        self.entries = []

    async def render_get(self, request):
        if not self.entries:
            payload = b"(aucun log)"
        else:
            payload = "\n".join(
                f"{i}: {e}" for i, e in enumerate(self.entries, 1)
            ).encode()
        return aiocoap.Message(code=aiocoap.Code.CONTENT, payload=payload)

    async def render_post(self, request):
        texte = request.payload.decode()
        self.entries.append(f"[{time.strftime('%H:%M:%S')}] {texte}")
        # Location-Path : /logs/<numéro de l'entrée>
        message = aiocoap.Message(code=aiocoap.Code.CREATED)
        message.opt.location_path = ("logs", str(len(self.entries)))
        return message

    async def render_delete(self, request):
        self.entries.clear()
        return aiocoap.Message(code=aiocoap.Code.DELETED)   # 2.02


# ---------------------------------------------------------
# Heure du serveur
# ---------------------------------------------------------
class TimeResource(resource.Resource):
    ct = 0

    async def render_get(self, request):
        return aiocoap.Message(
            code=aiocoap.Code.CONTENT,
            payload=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                  time.gmtime()).encode()
        )


# ---------------------------------------------------------
# Capteurs statiques : /sensors/room1/...
# ---------------------------------------------------------
class SensorResource(resource.Resource):
    ct = 0

    def __init__(self, valeur):
        super().__init__()
        self.valeur = valeur

    async def render_get(self, request):
        return aiocoap.Message(code=aiocoap.Code.CONTENT,
                               payload=self.valeur.encode())


# ---------------------------------------------------------
# Gros journal : déclenche le transfert blockwise
# ---------------------------------------------------------
class BigLogResource(resource.Resource):
    ct = 0

    async def render_get(self, request):
        lignes = "\n".join(
            f"Log {i}: capteur X - valeur {i*7 % 100}" for i in range(1, 61)
        )
        return aiocoap.Message(code=aiocoap.Code.CONTENT,
                               payload=lignes.encode())


# ---------------------------------------------------------
# Démarrage du serveur
# ---------------------------------------------------------
async def main():
    racine = resource.Site()
    temp = TemperatureResource()
    racine.add_resource(("temp",), temp)
    racine.add_resource(("led",), LedResource())
    racine.add_resource(("logs",), LogsResource())
    racine.add_resource(("time",), TimeResource())
    racine.add_resource(("sensors", "room1", "temperature"), SensorResource("23.5"))
    racine.add_resource(("sensors", "room1", "humidity"), SensorResource("55"))
    racine.add_resource(("sensors", "room1", "light"), SensorResource("150"))
    racine.add_resource(("biglog",), BigLogResource())
    # aiocoap 0.4 ne publie plus l'annuaire tout seul : on l'enregistre.
    racine.add_resource(
        (".well-known", "core"),
        resource.WKCResource(racine.get_resources_as_linkheader, impl_info=None),
    )

    # tâche de fond : fait "vivre" le capteur de température
    asyncio.get_running_loop().create_task(temp.background_task())

    # Le sujet indique bind=("::", 5683). aiocoap 0.4 sur Windows refuse
    # l'adresse générique : on retombe alors sur 127.0.0.1.
    try:
        await aiocoap.Context.create_server_context(racine, bind=("::", 5683))
    except ValueError:
        await aiocoap.Context.create_server_context(racine, bind=("127.0.0.1", 5683))
    print("=== SERVEUR CoAP DÉMARRÉ (port UDP 5683) ===")
    print("Ressources : /temp (observable), /led, /logs, /time")
    print("             /sensors/room1/{temperature,humidity,light}, /biglog")
    print("Ctrl+C pour arrêter.")
    await asyncio.Event().wait()   # tourne indéfiniment


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Serveur arrêté.")
