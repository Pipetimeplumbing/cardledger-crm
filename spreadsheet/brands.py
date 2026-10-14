"""Expandable collecting reference; family labels are not current ownership claims."""
GROUPS = {
    'Topps': ['Topps','Topps Chrome','Topps Chrome Update','Topps Chrome Sapphire','Topps Chrome Black','Topps Cosmic Chrome','Topps Chrome Platinum Anniversary','Topps Update','Topps Heritage','Topps Archives','Topps Archives Signature Series','Topps Allen & Ginter','Topps Stadium Club','Topps Stadium Club Chrome','Topps Finest','Topps Gold Label','Topps Gypsy Queen','Topps Gallery','Topps Fire','Topps Inception','Topps Museum Collection','Topps Triple Threads','Topps Tribute','Topps Tier One','Topps Five Star','Topps Dynasty','Topps Definitive','Topps Transcendent','Topps Big League','Topps Opening Day','Topps Pro Debut','Topps NOW','Topps Living Set','Topps T206','Topps Bundesliga','Topps UEFA Club Competitions','Topps Match Attax'],
    'Bowman': ['Bowman','Bowman Chrome','Bowman Draft','Bowman Sterling','Bowman Inception','Bowman Platinum',"Bowman's Best",'Bowman Heritage','Bowman University','Bowman University Chrome','Bowman University Best'],
    'Panini': ['Panini','Panini Prizm','Panini Select','Panini Mosaic','Panini Contenders','Panini Contenders Optic','Panini National Treasures','Panini Immaculate Collection','Panini Flawless','Panini One','Panini One and One','Panini Chronicles','Panini Obsidian','Panini Spectra','Panini Phoenix','Panini Origins','Panini Absolute','Panini Prestige','Panini Certified','Panini Limited','Panini Illusions','Panini Luminance','Panini Playbook','Panini XR','Panini Black','Panini Gold Standard','Panini Elite','Panini Court Kings','Panini Revolution','Panini Hoops','Panini NBA Hoops','Panini Noir','Panini Encased','Panini Crown Royale','Panini Impeccable','Panini Instant','Panini Adrenalyn XL'],
    'Donruss': ['Donruss','Donruss Optic','Donruss Elite','Donruss Elite Extra Edition','Donruss Classics','Donruss Threads','Donruss Signature Series','Donruss Studio','Donruss Diamond Kings','Donruss Americana','Donruss Leaf'],
    'Score': ['Score','Score Select','Score Summit','Score Pinnacle'],
    'Pinnacle': ['Pinnacle','Pinnacle Zenith','Pinnacle Certified','Pinnacle Aficionado','Pinnacle Inside'],
    'Upper Deck': ['Upper Deck','Upper Deck Series 1','Upper Deck Series 2','Upper Deck Extended Series','Upper Deck Young Guns','Upper Deck SP Authentic','Upper Deck SPx','Upper Deck SP Game Used','Upper Deck SP Signature','Upper Deck The Cup','Upper Deck Ultimate Collection','Upper Deck Premier','Upper Deck Exquisite Collection','Upper Deck Artifacts','Upper Deck Black Diamond','Upper Deck Clear Cut','Upper Deck Allure','Upper Deck Ice','Upper Deck Synergy','Upper Deck Trilogy','Upper Deck MVP','Upper Deck Credentials','Upper Deck Goodwin Champions','Upper Deck CHL','Upper Deck Parkhurst','Upper Deck Parkhurst Champions','Upper Deck O-Pee-Chee','Upper Deck O-Pee-Chee Platinum'],
    'Fleer': ['Fleer','Fleer Ultra','Fleer Tradition','Fleer Metal','Fleer Metal Universe','Fleer Flair','Fleer Flair Showcase','Fleer Focus','Fleer Mystique','Fleer E-X','Fleer Greats of the Game','Fleer Hot Prospects','Fleer Showcase'],
    'SkyBox': ['SkyBox','SkyBox Premium','SkyBox Metal Universe','SkyBox E-X','SkyBox E-X2000','SkyBox E-X2001','SkyBox Autographics','SkyBox Dominion','SkyBox Z-Force'],
    'Leaf': ['Leaf','Leaf Metal','Leaf Trinity','Leaf Valiant','Leaf Ultimate','Leaf Ultimate Draft','Leaf Pro Set','Leaf In The Game Used','Leaf Decadence','Leaf Lumber','Leaf Pop Century','Leaf Signature Series'],
    'Pro Set': ['Pro Set','Pro Set Platinum','Pro Set Power'],
    'O-Pee-Chee': ['O-Pee-Chee','O-Pee-Chee Premier'],
    'Pacific': ['Pacific','Pacific Crown Royale','Pacific Revolution','Pacific Prism','Pacific Prizm','Pacific Invincible','Pacific Private Stock','Pacific Vanguard','Pacific Titanium','Pacific Cramer'],
    'In The Game': ['In The Game','In The Game Heroes and Prospects','In The Game Between the Pipes','In The Game Ultimate Memorabilia','In The Game Superlative'],
    'Press Pass': ['Press Pass','Press Pass SE','Press Pass Legends','Press Pass Showcase','Press Pass Eclipse','Press Pass Premium'],
    'SAGE': ['SAGE','SAGE HIT','SAGE Aspire','SAGE Autographed'],
    'Classic': ['Classic','Classic Four Sport','Classic Draft Picks','Classic Best'],
    'Other / historical': ['Action Packed','Arena Club','A&BC','Best','Broders','Cracker Jack','Dover','Goodwin & Company','Goudey','Gum Inc.','Honus Bonus','Kellogg\'s','Lone Star','Mother\'s Cookies','Onyx','Parkhurst','Post','Rittenhouse','Royal Rookies','Sport Kings','TCMA','Tobacco cards (T-series)','Tristar','Tristar Hidden Treasures','Tristar Obak','Wild Card','Wizards of the Coast MLB Showdown','Zee-Nut','Custom / other']
}

def catalog():
    rows=[]
    for family, names in GROUPS.items():
        for name in names:
            kind = 'Brand / maker' if name == family else 'Product line / collecting label'
            note = 'Historical family label; manufacturer and licensing vary by release year.'
            if name == 'Upper Deck Young Guns':
                kind='Insert / rookie subset';note='Young Guns is a subset, not a separate manufacturer.'
            if name == 'Custom / other':note='Use this or enter a custom name for releases not listed.'
            rows.append((name,family,kind,note))
    return sorted(rows,key=lambda row:row[0].casefold())
