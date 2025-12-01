
def notify_subscriber_template(header, news_content, user_email):    
    html_content = f"""
        <!DOCTYPE html>
            <html>
                <head>
                    <meta charset="UTF-8" />
                    <style>
                        body {{
                            margin: 0;
                            padding: 0;
                            background: #f6f7f9;
                            font-family: Helvetica, Arial, sans-serif;
                            color: #333;
                        }}
                        .container {{
                            max-width: 620px;
                            margin: 30px auto;
                            background: #ffffff;
                            border-radius: 8px;
                            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                            overflow: hidden;
                        }}
                        .header {{
                            background: #1a2332;
                            color: #ffffff;
                            padding: 28px;
                            text-align: center;
                        }}
                        .header h1 {{
                            margin: 0;
                            font-size: 26px;
                            font-weight: 600;
                        }}
                        .content {{
                            padding: 32px;
                            line-height: 1.65;
                            font-size: 16px;
                        }}
                        .content h2 {{
                            margin-top: 28px;
                            font-size: 20px;
                            color: #1a2332;
                        }}
                        .content p {{
                            margin: 12px 0 18px;
                        }}
                        .footer {{
                            text-align: center;
                            padding: 22px;
                            font-size: 12px;
                            background: #f1f3f6;
                            color: #777;
                        }}
                    </style>
                </head>

            <body>
                <div class="container">
                    <div class="header">
                        <h1>{header}</h1>
                    </div>

                    <div class="content">
                        {news_content}
                        <p>Thank you for reading today’s briefing. Stay informed and ahead.</p>
                    </div>

                    <div class="footer">
                        This update was sent to <strong>{user_email}</strong><br />
                        © 2025 NewsPluk, Kathmandu, Nepal. All rights reserved.
                    </div>
                </div>
            </body>
        </html>
    """
    return html_content