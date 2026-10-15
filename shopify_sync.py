"""Explicit, one-way draft product sync using Shopify's Admin GraphQL API."""
import json
import os
import re
import urllib.request
import urllib.error

API_VERSION='2026-07'

def configuration():
    keys=('SHOPIFY_STORE_DOMAIN','SHOPIFY_ADMIN_ACCESS_TOKEN','SHOPIFY_LOCATION_ID')
    values={key:os.environ.get(key,'').strip() for key in keys}
    missing=[key for key,value in values.items() if not value]
    domain=values['SHOPIFY_STORE_DOMAIN']
    valid=bool(re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com',domain))
    return values,missing,valid

class Shopify:
    def __init__(self):
        values,missing,valid=configuration()
        if missing:raise ValueError('Connect Shopify first. Missing settings: '+', '.join(missing))
        if not valid:raise ValueError('Use your store’s original name.myshopify.com domain.')
        self.store=values['SHOPIFY_STORE_DOMAIN'];self.token=values['SHOPIFY_ADMIN_ACCESS_TOKEN']
        location=values['SHOPIFY_LOCATION_ID']
        if location.isdigit():location='gid://shopify/Location/'+location
        if not re.fullmatch(r'gid://shopify/Location/\d+',location):raise ValueError('Enter a valid Shopify location ID.')
        self.location=location

    def graphql(self,query,variables):
        payload=json.dumps({'query':query,'variables':variables}).encode()
        request=urllib.request.Request(f'https://{self.store}/admin/api/{API_VERSION}/graphql.json',data=payload,headers={'Content-Type':'application/json','X-Shopify-Access-Token':self.token})
        try:
            with urllib.request.urlopen(request,timeout=30) as response:result=json.load(response)
        except (urllib.error.URLError,TimeoutError,json.JSONDecodeError):
            raise ValueError('Shopify could not be reached or rejected access. Check the connection and app permissions.')
        if result.get('errors'):raise ValueError('Shopify rejected this API request. Check app permissions and the API version.')
        return result.get('data',{})

    def mutation(self,query,variables,key):
        result=self.graphql(query,variables).get(key)
        if not result:raise ValueError('Shopify returned an unexpected response.')
        if result.get('userErrors'):
            raise ValueError('Shopify: '+'; '.join(str(e.get('message','Request rejected')) for e in result['userErrors']))
        return result

    def create(self,card):
        title=' · '.join(str(card[k]) for k in ('player','year','brand','subset','grade','serial_number') if card[k])
        data={'title':title,'handle':f'cardledger-{card["id"]}','vendor':card['brand'],'productType':card['sport'],'status':'DRAFT','tags':['CardLedger',card['sport']]}
        result=self.mutation('mutation($product:ProductCreateInput!){productCreate(product:$product){product{id variants(first:1){nodes{id inventoryItem{id}}}} userErrors{field message}}}',{'product':data},'productCreate')
        product=result['product'];variant=product['variants']['nodes'][0]
        return product['id'],variant['id'],variant['inventoryItem']['id']

    def validate_currency(self):
        data=self.graphql('query { shop { currencyCode } }',{})
        if data.get('shop',{}).get('currencyCode')!='USD':raise ValueError('CardLedger prices are USD. Connect a USD Shopify store or add currency conversion before syncing.')

    def quantity(self,item):
        result=self.graphql('query($item:ID!,$location:ID!){inventoryItem(id:$item){inventoryLevel(locationId:$location){quantities(names:["available"]){name quantity}}}}',{'item':item,'location':self.location})
        inventory=result.get('inventoryItem')
        if not inventory:raise ValueError('The Shopify inventory item no longer exists. Review the product in Shopify.')
        level=inventory.get('inventoryLevel')
        if level is None:return None
        return next((q['quantity'] for q in level['quantities'] if q['name']=='available'),0)

    def activate(self,item):
        self.mutation('mutation($item:ID!,$location:ID!){inventoryActivate(inventoryItemId:$item,locationId:$location){inventoryLevel{id} userErrors{field message}}}',{'item':item,'location':self.location},'inventoryActivate')

    def update_price(self,product,variant,card):
        self.mutation('mutation($product:ID!,$variants:[ProductVariantsBulkInput!]!){productVariantsBulkUpdate(productId:$product,variants:$variants){productVariants{id} userErrors{field message}}}',{'product':product,'variants':[{'id':variant,'price':f'{card["market_price"]/100:.2f}','inventoryItem':{'sku':f'CL-{card["id"]}','tracked':True}}]},'productVariantsBulkUpdate')

    def set_quantity(self,item,quantity,compare_quantity):
        self.mutation('mutation($input:InventorySetQuantitiesInput!){inventorySetQuantities(input:$input){inventoryAdjustmentGroup{createdAt} userErrors{field message}}}',{'input':{'name':'available','reason':'correction','quantities':[{'inventoryItemId':item,'locationId':self.location,'quantity':quantity,'compareQuantity':compare_quantity}]}},'inventorySetQuantities')
