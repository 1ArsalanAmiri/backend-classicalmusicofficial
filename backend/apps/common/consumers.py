import json
from channels.generic.websocket import AsyncWebsocketConsumer


class AlbumZipConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.album_slug = self.scope['url_route']['kwargs']['album_slug']
        self.group_name = f"album_{self.album_slug}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({"status": "connected", "message": "Listening for zip status..."}))


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def zip_status(self, event):
        print(f"--- WEBSOCKET RECEIVED EVENT IN CONSUMER ---")
        print(event)
        print("--------------------------------------------")
        if 'message' in event:
            await self.send(text_data=json.dumps(event["message"]))
        else:
            print(f"WARNING: 'message' key not found in event: {event}")
            await self.send(text_data=json.dumps({"error": "Invalid event format", "event": event}))
