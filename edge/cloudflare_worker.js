export default {
  async fetch(request, env, ctx) {
    // Only accept POST requests to /webhook
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/webhook") {
      return new Response("Not Found", { status: 404 });
    }

    try {
      const payload = await request.json();

      // Check if it's a message from Telegram
      if (payload.message && payload.message.chat && payload.message.chat.id) {
        const chatId = payload.message.chat.id;

        // Immediately reply and pin a message to stop Telegram retry loop
        // We will use ctx.waitUntil for actual processing

        ctx.waitUntil(this.processWebhook(payload, env));

        // Return 200 OK immediately
        return new Response("OK", { status: 200 });
      }

      return new Response("OK", { status: 200 });
    } catch (e) {
      return new Response("Bad Request", { status: 400 });
    }
  },

  async processWebhook(payload, env) {
    const chatId = payload.message.chat.id;
    const botToken = env.TELEGRAM_BOT_TOKEN;
    const hfSpaceUrl = env.HF_SPACE_URL; // e.g., https://your-space.hf.space

    // 1. Send initial message
    const sendMsgResponse = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId,
        text: "🚀 **Live Mission Control Dashboard**\n\nInitializing Autonomous Multi-Agent OS...\n⏳ Analyzing Business Thought...",
        parse_mode: "Markdown"
      })
    });

    if (sendMsgResponse.ok) {
      const msgData = await sendMsgResponse.json();
      const messageId = msgData.result.message_id;

      // 2. Pin the message
      await fetch(`https://api.telegram.org/bot${botToken}/pinChatMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          message_id: messageId,
          disable_notification: true
        })
      });

      // Add message_id to payload so backend can edit this pinned message
      payload.mission_control_message_id = messageId;
    }

    // 3. Forward to Hugging Face Space FastAPI Engine
    if (hfSpaceUrl) {
      await fetch(`${hfSpaceUrl}/api/v1/orchestrate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${env.API_SECRET || ''}`
        },
        body: JSON.stringify(payload)
      });
    }
  }
};
