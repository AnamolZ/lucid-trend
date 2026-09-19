def notify_subscriber_template(header: str, news_content: str, user_email: str) -> str:
    """
    Renders a responsive, modern HTML email template for daily tech intelligence updates.
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{header}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #0b0f19;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            -webkit-font-smoothing: antialiased;
        }}
        .wrapper {{
            width: 100%;
            background-color: #0b0f19;
            padding: 40px 10px;
        }}
        .container {{
            max-width: 640px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }}
        .header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            padding: 36px 30px;
            text-align: center;
            border-bottom: 3px solid #6366f1;
        }}
        .header .badge {{
            display: inline-block;
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid #818cf8;
            color: #c7d2fe;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            padding: 4px 12px;
            border-radius: 20px;
            margin-bottom: 12px;
        }}
        .header h1 {{
            margin: 0;
            color: #ffffff;
            font-size: 24px;
            font-weight: 700;
            line-height: 1.3;
        }}
        .content {{
            padding: 36px 32px;
            line-height: 1.7;
            font-size: 15px;
            color: #334155;
        }}
        .content h2 {{
            margin-top: 28px;
            margin-bottom: 12px;
            font-size: 19px;
            font-weight: 700;
            color: #0f172a;
            border-left: 4px solid #6366f1;
            padding-left: 12px;
        }}
        .content p {{
            margin: 0 0 18px 0;
        }}
        .divider {{
            height: 1px;
            background: #e2e8f0;
            margin: 28px 0;
        }}
        .closing {{
            margin-top: 24px;
            padding: 16px;
            background: #f8fafc;
            border-radius: 8px;
            font-size: 14px;
            color: #64748b;
            text-align: center;
        }}
        .footer {{
            background: #0f172a;
            padding: 24px 20px;
            text-align: center;
            font-size: 12px;
            color: #94a3b8;
            line-height: 1.6;
        }}
        .footer a {{
            color: #818cf8;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="container">
            <div class="header">
                <div class="badge">Daily Tech Intelligence</div>
                <h1>{header}</h1>
            </div>
            <div class="content">
                {news_content}
                <div class="closing">
                    💡 <em>Curated by NewsPluk Autonomous AI Engine. Delivering developer-centric, verified technical news daily.</em>
                </div>
            </div>
            <div class="footer">
                You received this briefing because you subscribed at <a href="https://newspluk.com">newspluk.com</a>.<br>
                Dispatched to: <strong>{user_email}</strong><br>
                © 2026 NewsPluk, Inc. All rights reserved.
            </div>
        </div>
    </div>
</body>
</html>"""