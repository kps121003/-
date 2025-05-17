import discord
from discord.ext import commands
from discord.ui import View, button, Select

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 관리자 ID (본인 Discord ID로 바꾸세요)
ADMIN_IDS = {1367850607783837778}

# 제품과 가격
products = {
    "외주서비스": 3000,
    "테러봇노빡고": 12000,
    "테러봇빡고용": 19000,
}

# 사용자 정보: user_id: {"name": str, "account": str, "balance": int}
user_data = {}

# 거래 로그 기록용 채널 ID (있으면)
LOG_CHANNEL_ID = None  # 예: 123456789012345678

class VendingMachineView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @button(label="구매", style=discord.ButtonStyle.primary, custom_id="buy_button")
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return
        
        options = [discord.SelectOption(label=p, description=f"{price}원") for p, price in products.items()]
        select = ProductSelect(self.user_id, options)
        view = View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("구매할 상품을 선택하세요:", view=view, ephemeral=True)

    @button(label="내 정보", style=discord.ButtonStyle.success, custom_id="info_button")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return
        
        data = user_data.get(self.user_id, {"name":"등록 안됨","account":"등록 안됨","balance":0})
        embed = discord.Embed(title=f"{interaction.user.name}님의 정보", color=discord.Color.green())
        embed.add_field(name="이름", value=data.get("name", "등록 안됨"), inline=False)
        embed.add_field(name="계좌번호", value=data.get("account", "등록 안됨"), inline=False)
        embed.add_field(name="잔액", value=f"{data.get('balance', 0)}원", inline=False)
        view = UserInfoEditView(self.user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @button(label="제품 목록", style=discord.ButtonStyle.secondary, custom_id="product_list_button")
    async def product_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="제품 목록", color=discord.Color.blue())
        for product, price in products.items():
            embed.add_field(name=product, value=f"{price}원", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ProductSelect(discord.ui.Select):
    def __init__(self, user_id, options):
        super().__init__(placeholder="상품을 선택하세요", min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 선택창은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return

        product_name = self.values[0]
        price = products[product_name]
        data = user_data.get(self.user_id, {"balance": 0})
        balance = data.get("balance", 0)

        if balance < price:
            await interaction.response.send_message(f"잔액이 부족합니다. ({balance}원 보유, {price}원 필요)", ephemeral=True)
            return

        # 구매 재확인 뷰
        view = ConfirmPurchaseView(self.user_id, product_name, price)
        await interaction.response.send_message(f"'{product_name}' 을(를) {price}원에 구매하시겠습니까?", view=view, ephemeral=True)


class ConfirmPurchaseView(View):
    def __init__(self, user_id, product, price):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.product = product
        self.price = price

    @button(label="예", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return

        # 잔액 재확인
        data = user_data.get(self.user_id, {"balance":0})
        balance = data.get("balance", 0)
        if balance < self.price:
            await interaction.response.send_message("잔액이 부족합니다. 구매할 수 없습니다.", ephemeral=True)
            return

        # 차감 및 저장
        data["balance"] = balance - self.price
        user_data[self.user_id] = data

        # 사용자에게 구매완료 메시지 DM 전송
        try:
            await interaction.user.send(f"'{self.product}' 구매해주셔서 감사합니다! 관리자가 곧 제공해 드릴 것입니다.")
        except discord.Forbidden:
            pass

        # 관리 로그 채널에 알림 (있으면)
        if LOG_CHANNEL_ID:
            channel = bot.get_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(f"사용자 {interaction.user} 님이 '{self.product}' 을(를) {self.price}원에 구매했습니다. 남은 잔액: {data['balance']}원")

        await interaction.response.send_message(f"'{self.product}' 구매가 완료되었습니다! 감사합니다.", ephemeral=True)
        self.stop()

    @button(label="아니오", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return
        await interaction.response.send_message("구매가 취소되었습니다.", ephemeral=True)
        self.stop()

class UserInfoEditView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @button(label="정보 수정하기", style=discord.ButtonStyle.primary)
    async def edit_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 당신을 위한 것이 아닙니다!", ephemeral=True)
            return
        # DM으로 이름, 계좌 수정 안내
        try:
            await interaction.user.send("이름과 계좌번호를 입력해주세요. 각각 한 줄씩 입력해주세요.\n예:\n홍길동\n123-456-789")
            bot.waiting_for_edit = interaction.user.id  # 플래그 설정
            await interaction.response.send_message("DM으로 정보를 입력해주세요.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("DM이 차단되어 있습니다. DM을 열어주세요.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 정보 수정 대기중일 때 DM 처리
    if isinstance(message.channel, discord.DMChannel):
        if getattr(bot, "waiting_for_edit", None) == message.author.id:
            lines = message.content.strip().split('\n')
            if len(lines) >= 2:
                name = lines[0].strip()
                account = lines[1].strip()
                data = user_data.get(message.author.id, {"balance":0})
                data["name"] = name
                data["account"] = account
                user_data[message.author.id] = data
                await message.channel.send(f"이름과 계좌번호가 수정되었습니다.\n이름: {name}\n계좌: {account}")
                bot.waiting_for_edit = None
            else:
                await message.channel.send("입력 형식이 올바르지 않습니다. 이름과 계좌번호를 각각 한 줄씩 입력해주세요.")
            return

    await bot.process_commands(message)

# 관리자 전용 돈추가, 돈회수, 돈조회 명령어
def is_admin():
    async def predicate(ctx):
        return ctx.author.id in ADMIN_IDS
    return commands.check(predicate)

@bot.command()
@is_admin()
async def 돈추가(ctx, user_id: int, amount: int):
    data = user_data.get(user_id, {"balance":0, "name":"", "account":""})
    data["balance"] = data.get("balance", 0) + amount
    user_data[user_id] = data

    # 대상에게 DM으로 알림
    member = ctx.guild.get_member(user_id)
    if member:
        try:
            await member.send(f"{ctx.author.name}님이 당신의 자판기 잔액에 {amount}원을 충전해주셨습니다.")
        except discord.Forbidden:
            pass
    await ctx.send(f"{user_id}님의 잔액이 {amount}원만큼 충전되었습니다.")

@bot.command()
@is_admin()
async def 돈회수(ctx, user_id: int, amount: int):
    data = user_data.get(user_id, {"balance":0})
    current = data.get("balance", 0)
    data["balance"] = max(0, current - amount)
    user_data[user_id] = data
    await ctx.send(f"{user_id}님의 잔액에서 {amount}원이 차감되었습니다.")

@bot.command()
@is_admin()
async def 돈조회(ctx, user_id: int):
    data = user_data.get(user_id, {"balance":0})
    await ctx.send(f"{user_id}님의 잔액은 {data.get('balance',0)}원입니다.")

@bot.command()
async def 자판기(ctx):
    user_id = ctx.author.id
    if user_id not in user_data:
        user_data[user_id] = {"name": "", "account": "", "balance": 0}

    embed = discord.Embed(
        title="🛒 CTY 자판기",
        description="원하는 상품을 아래 버튼에서 선택하세요!",
        color=discord.Color.blue()
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1367852169105244282/1372135211114168390/ChatGPT_Image_2025_5_14_05_55_13.png?ex=6829a07f&is=68284eff&hm=df0700ee7f3a4671382a7a2319d4ef1f7fa612ec772824ba6eca3f5f1a630c97&")
    embed.set_footer(text="© CTY 자판기 봇")

    view = VendingMachineView(user_id)
    await ctx.send(content=f"{ctx.author.mention}님, 자판기에 오신 것을 환영합니다!", embed=embed, view=view)


bot.run("MTM3MzIzMDc3Mzk2ODA0NDA2Mg.GNQLKx.aIktPt2HI7lVknB3HYbndXFGi9Bo2TTePz5LP8")
