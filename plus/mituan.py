
import json
import urllib3
from urllib.parse import urlencode
import save_to_excel
import requests

session_id="3b4a33f108c520cc74bd91db21ec73c4"

def get_exhibition_list(pagenum):
    url="https://shmthz.kyson.com.cn"
    params={
        "s":"/ApiHotel/getprolist",
        "aid":1,
        "platform":"wx",
        "session_id":session_id,
        "pid":0,
        "pagenum":pagenum,
        "keyword":"",
        "idList":"",
        "start_time":"",
        "end_time":""
    }
    headers={}
    datas={}
    request_params = {
        "headers": headers,
        "data":datas
    }
    request_params['params'] = urlencode(params)
    response = requests.post(url, **request_params, verify=False)
    response.raise_for_status()
    return json.loads(response.content)
def get_hotel_list(exhibition_id):
    url="https://shmthz.kyson.com.cn"
    params={
        "s":"/ApiShop/getprolist",
        "aid":1,
        "platform":"wx",
        "session_id":session_id,
        "pid":0
    }
    headers={
        "Content-Type":"application/json"
    }
    datas={
        "pagenum":1,
        "keyword":"",
        "field":"",
        "order":"",
        "cid":exhibition_id,
        "cid2":"",
        "cpid":0,
        "bid":""
    }
    request_params = {
        "headers": headers,
        "params":urlencode(params),
        "data":datas
    }
    response = requests.post(url, **request_params, verify=False)
    response.raise_for_status()
    return json.loads(response.content)["data"]

def get_room_list(hotel_id):
    url = "https://shmthz.kyson.com.cn"
    params = {
        "s": "/ApiShop/product",
        "aid": 1,
        "platform": "wx",
        "session_id": session_id,
        "pid": 0,
        "id":hotel_id
    }
    headers = {
        "Content-Type": "application/json"
    }
    datas = {}
    request_params = {
        "headers": headers,
        "params": urlencode(params),
        "data": datas
    }
    response = requests.post(url, **request_params, verify=False)
    response.raise_for_status()
    return json.loads(response.content)["guige"]
def main():
    pagenum=1
    previous_exhibitions=[]
    while True: 
        exhibitions=get_exhibition_list(pagenum)
        if len(exhibitions)==0:
            print("No more data available.", flush=True)
            break

        if exhibitions == previous_exhibitions:
            print("No new data found. Exiting.", flush=True)
            break

        previous_exhibitions = exhibitions
        exhibition_index=0
        print(f"已获取第{pagenum}页{len(exhibitions)}条展会信息")
        while exhibition_index<len(exhibitions): #len(exhibitions)
            exhibition=exhibitions[exhibition_index]
            #保存展会信息
            exhibition_name=exhibition["name"]
            site = exhibition["address"]
            zg = exhibition["huizhan"]
            start_time= exhibition["start_time"]
            end_time = exhibition["end_time"]

            hotels=get_hotel_list(exhibition["id"])
            hotel_index=0
            print(f"已获取{exhibition_name}共{len(hotels)}条酒店信息")
            while hotel_index<len(hotels):
                hotel=hotels[hotel_index]
                #保存酒店信息
                hotel_name = hotel["name"]
                hotel_address = hotel["sellpoint"]
                sell_price= hotel["sell_price"]
                peitao = hotel["peitao"]
                xianzhi = hotel["xianzhi"]
                xiangqing = hotel["xiangqing"]

                rooms=get_room_list(hotel["id"])
                room_index=0
                datasets = []
                print(f"已获取{hotel_name}共{len(rooms)}条房型信息")
                while room_index<len(rooms):
                    room=rooms[room_index]
                    datarecords = {}
                    # 保存展会信息
                    datarecords["exhibition_name"] = exhibition_name
                    datarecords["site"] = site
                    datarecords["zg"] = zg
                    datarecords["start_time"] =start_time
                    datarecords["end_time"] = end_time
                    # 保存酒店信息
                    datarecords["hotel_name"] =hotel_name
                    datarecords["hotel_address"] = hotel_address
                    datarecords["sell_price"] =sell_price
                    datarecords["peitao"] =peitao
                    datarecords["xianzhi"] = xianzhi
                    datarecords["xiangqing"] =xiangqing
                    #保存房型信息
                    datarecords["type_name"] = room["name"]
                    datarecords["type_sell_price"] = room["sell_price"]
                    datarecords["type_peitao"] = room["peitao"]
                    datarecords["type_xianzhi"] = room["xianzhi"]
                    datarecords["type_xiangqing"] = room["xiangqing"]
                    datasets.append(datarecords)
                    room_index=room_index+1

                save_to_excel.save(datasets,"meituan")
                print(f"--------------已成功保存{hotel_name}房型信息--------------")
                hotel_index=hotel_index+1
            exhibition_index=exhibition_index+1
        pagenum=pagenum+1
if __name__ == "__main__":
    urllib3.disable_warnings()
    main()