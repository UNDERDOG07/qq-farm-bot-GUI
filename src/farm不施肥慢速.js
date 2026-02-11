/**
 * 自己的农场操作 - 收获/种植/商店/巡田（不施肥、不浇水、不除草、不除虫 速度恢复版）
 */
const protobuf = require('protobufjs');
const { CONFIG, PlantPhase, PHASE_NAMES } = require('./config');
const { types } = require('./proto');
const { sendMsgAsync, getUserState, networkEvents } = require('./network');
const { toLong, toNum, getServerTimeSec, toTimeSec, log, logWarn, sleep } = require('./utils');
const { getPlantNameBySeedId, getPlantName, getPlantExp, formatGrowTime, getPlantGrowTime } = require('./gameConfig');

// ============ 内部状态 ============
let isCheckingFarm = false;
let isFirstFarmCheck = true;
let farmCheckTimer = null;
let farmLoopRunning = false;

// ============ 农场 API ============
let onOperationLimitsUpdate = null;
function setOperationLimitsCallback(callback) {
    onOperationLimitsUpdate = callback;
}

async function getAllLands() {
    const body = types.AllLandsRequest.encode(types.AllLandsRequest.create({})).finish();
    const { body: replyBody } = await sendMsgAsync('gamepb.plantpb.PlantService', 'AllLands', body);
    const reply = types.AllLandsReply.decode(replyBody);
    if (reply.operation_limits && onOperationLimitsUpdate) {
        onOperationLimitsUpdate(reply.operation_limits);
    }
    return reply;
}

async function harvest(landIds) {
    const state = getUserState();
    const body = types.HarvestRequest.encode(types.HarvestRequest.create({
        land_ids: landIds,
        host_gid: toLong(state.gid),
        is_all: true,
    })).finish();
    const { body: replyBody } = await sendMsgAsync('gamepb.plantpb.PlantService', 'Harvest', body);
    return types.HarvestReply.decode(replyBody);
}

async function removePlant(landIds) {
    const body = types.RemovePlantRequest.encode(types.RemovePlantRequest.create({
        land_ids: landIds.map(id => toLong(id)),
    })).finish();
    const { body: replyBody } = await sendMsgAsync('gamepb.plantpb.PlantService', 'RemovePlant', body);
    return types.RemovePlantReply.decode(replyBody);
}

// ============ 商店 API ============
async function getShopInfo(shopId) {
    const body = types.ShopInfoRequest.encode(types.ShopInfoRequest.create({
        shop_id: toLong(shopId),
    })).finish();
    const { body: replyBody } = await sendMsgAsync('gamepb.shoppb.ShopService', 'ShopInfo', body);
    return types.ShopInfoReply.decode(replyBody);
}

async function buyGoods(goodsId, num, price) {
    const body = types.BuyGoodsRequest.encode(types.BuyGoodsRequest.create({
        goods_id: toLong(goodsId),
        num: toLong(num),
        price: toLong(price),
    })).finish();
    const { body: replyBody } = await sendMsgAsync('gamepb.shoppb.ShopService', 'BuyGoods', body);
    return types.BuyGoodsReply.decode(replyBody);
}

// ============ 种植 ============
function encodePlantRequest(seedId, landIds) {
    const writer = protobuf.Writer.create();
    const itemWriter = writer.uint32(18).fork();
    itemWriter.uint32(8).int64(seedId);
    const idsWriter = itemWriter.uint32(18).fork();
    for (const id of landIds) {
        idsWriter.int64(id);
    }
    idsWriter.ldelim();
    itemWriter.ldelim();
    return writer.finish();
}

async function plantSeeds(seedId, landIds) {
    let successCount = 0;
    for (const landId of landIds) {
        try {
            const body = encodePlantRequest(seedId, [landId]);
            const { body: replyBody } = await sendMsgAsync('gamepb.plantpb.PlantService', 'Plant', body);
            types.PlantReply.decode(replyBody);
            successCount++;
        } catch (e) {
            logWarn('种植', `土地#${landId} 失败: ${e.message}`);
        }
        if (landIds.length > 1) await sleep(50); // 保留原 50ms 逐块间隔
    }
    return successCount;
}

async function findBestSeed() {
    const SEED_SHOP_ID = 2;
    const shopReply = await getShopInfo(SEED_SHOP_ID);
    if (!shopReply.goods_list || shopReply.goods_list.length === 0) {
        logWarn('商店', '种子商店无商品');
        return null;
    }
    const state = getUserState();
    const available = [];
    for (const goods of shopReply.goods_list) {
        if (!goods.unlocked) continue;
        let meetsConditions = true;
        let requiredLevel = 0;
        const conds = goods.conds || [];
        for (const cond of conds) {
            if (toNum(cond.type) === 1) {
                requiredLevel = toNum(cond.param);
                if (state.level < requiredLevel) {
                    meetsConditions = false;
                    break;
                }
            }
        }
        if (!meetsConditions) continue;
        const limitCount = toNum(goods.limit_count);
        const boughtNum = toNum(goods.bought_num);
        if (limitCount > 0 && boughtNum >= limitCount) continue;
        available.push({
            goods,
            goodsId: toNum(goods.id),
            seedId: toNum(goods.item_id),
            price: toNum(goods.price),
            requiredLevel,
        });
    }
    if (available.length === 0) {
        logWarn('商店', '没有可购买的种子');
        return null;
    }
    available.sort((a, b) => a.requiredLevel - b.requiredLevel); // 优先白萝卜
    return available[0];
}

async function autoPlantEmptyLands(deadLandIds, emptyLandIds) {
    let landsToPlant = [...emptyLandIds];
    const state = getUserState();

    // 1. 铲除枯死/收获残留
    if (deadLandIds.length > 0) {
        try {
            await removePlant(deadLandIds);
            log('铲除', `已铲除 ${deadLandIds.length} 块`);
        } catch (e) {
            logWarn('铲除', `失败: ${e.message}`);
        }
        landsToPlant.push(...deadLandIds);
    }

    if (landsToPlant.length === 0) return;

    // 2. 种子商店
    let bestSeed;
    try {
        bestSeed = await findBestSeed();
    } catch (e) {
        logWarn('商店', `查询失败: ${e.message}`);
        return;
    }
    if (!bestSeed) return;

    const seedName = getPlantNameBySeedId(bestSeed.seedId);
    const growTime = getPlantGrowTime(1020000 + (bestSeed.seedId - 20000));
    const growTimeStr = growTime > 0 ? ` 生长${formatGrowTime(growTime)}` : '';
    log('商店', `选择种子: ${seedName} (${bestSeed.seedId}) 价格=${bestSeed.price}金币${growTimeStr}`);

    // 3. 购买
    const needCount = landsToPlant.length;
    const totalCost = bestSeed.price * needCount;
    if (totalCost > state.gold) {
        logWarn('商店', `金币不足! 需要 ${totalCost}，当前 ${state.gold}`);
        const canBuy = Math.floor(state.gold / bestSeed.price);
        if (canBuy <= 0) return;
        landsToPlant = landsToPlant.slice(0, canBuy);
        log('商店', `金币有限，只种 ${canBuy} 块`);
    }

    let actualSeedId = bestSeed.seedId;
    try {
        const buyReply = await buyGoods(bestSeed.goodsId, landsToPlant.length, bestSeed.price);
        if (buyReply.get_items && buyReply.get_items.length > 0) {
            const gotItem = buyReply.get_items[0];
            actualSeedId = toNum(gotItem.id);
        }
        if (buyReply.cost_items) {
            for (const item of buyReply.cost_items) {
                state.gold -= toNum(item.count);
            }
        }
        const boughtName = getPlantNameBySeedId(actualSeedId);
        log('购买', `已购买 ${boughtName}种子 x${landsToPlant.length}，花费 ${bestSeed.price * landsToPlant.length} 金币`);
    } catch (e) {
        logWarn('购买', e.message);
        return;
    }

    // 4. 种植
    let plantedLands = [];
    try {
        const planted = await plantSeeds(actualSeedId, landsToPlant);
        log('种植', `已在 ${planted} 块地种植`);
        if (planted > 0) {
            plantedLands = landsToPlant.slice(0, planted);
        }
    } catch (e) {
        logWarn('种植', e.message);
    }

    // 5. 施肥 - 已禁用
    if (plantedLands.length > 0) {
        log('施肥', '已禁用施肥操作（不施肥版本）');
    }
}

// ============ 土地分析（只关心可收、枯死、空地） ============
function getCurrentPhase(phases, debug, landLabel) {
    if (!phases || phases.length === 0) return null;
    const nowSec = getServerTimeSec();
    for (let i = phases.length - 1; i >= 0; i--) {
        const beginTime = toTimeSec(phases[i].begin_time);
        if (beginTime > 0 && beginTime <= nowSec) {
            return phases[i];
        }
    }
    return phases[0];
}

function analyzeLands(lands) {
    const result = {
        harvestable: [],
        empty: [],
        dead: [],
        harvestableInfo: [],
    };

    for (const land of lands) {
        const id = toNum(land.id);
        if (!land.unlocked) continue;

        const plant = land.plant;
        if (!plant || !plant.phases || plant.phases.length === 0) {
            result.empty.push(id);
            continue;
        }

        const currentPhase = getCurrentPhase(plant.phases, false, `土地#${id}`);
        if (!currentPhase) {
            result.empty.push(id);
            continue;
        }

        const phaseVal = currentPhase.phase;
        if (phaseVal === PlantPhase.DEAD) {
            result.dead.push(id);
            continue;
        }
        if (phaseVal === PlantPhase.MATURE) {
            result.harvestable.push(id);
            const plantId = toNum(plant.id);
            const plantName = getPlantName(plantId) || '未知';
            const plantExp = getPlantExp(plantId);
            result.harvestableInfo.push({ landId: id, plantId, name: plantName, exp: plantExp });
            continue;
        }
        // 其他状态忽略
    }

    return result;
}

// ============ 巡田主循环 ============
async function checkFarm() {
    const state = getUserState();
    if (isCheckingFarm || !state.gid) return;
    isCheckingFarm = true;
    try {
        const landsReply = await getAllLands();
        if (!landsReply.lands || landsReply.lands.length === 0) {
            log('农场', '没有土地数据');
            return;
        }
        const lands = landsReply.lands;
        const status = analyzeLands(lands);
        isFirstFarmCheck = false;

        const statusParts = [];
        if (status.harvestable.length) statusParts.push(`收:${status.harvestable.length}`);
        if (status.dead.length) statusParts.push(`枯:${status.dead.length}`);
        if (status.empty.length) statusParts.push(`空:${status.empty.length}`);
        statusParts.push(`长:${lands.length - status.harvestable.length - status.dead.length - status.empty.length}`);

        const hasWork = status.harvestable.length || status.dead.length || status.empty.length;

        const actions = [];

        // 收获
        if (status.harvestable.length > 0) {
            try {
                await harvest(status.harvestable);
                actions.push(`收获${status.harvestable.length}`);
            } catch (e) {
                logWarn('收获', e.message);
            }
        }

        // 铲除 + 种植
        const allDeadLands = [...status.dead, ...status.harvestable];
        const allEmptyLands = [...status.empty];
        if (allDeadLands.length > 0 || allEmptyLands.length > 0) {
            try {
                await autoPlantEmptyLands(allDeadLands, allEmptyLands);
                actions.push(`种植${allDeadLands.length + allEmptyLands.length}`);
            } catch (e) {
                logWarn('种植循环', e.message);
            }
        }

        const actionStr = actions.length > 0 ? ` → ${actions.join(' / ')}` : '';
        if (hasWork || isFirstFarmCheck) {
            log('农场', `[${statusParts.join(' ')}]${actionStr}${!hasWork ? ' 无需操作' : ''}`);
        }
    } catch (err) {
        logWarn('巡田', `检查失败: ${err.message}`);
    } finally {
        isCheckingFarm = false;
    }
}

async function farmCheckLoop() {
    while (farmLoopRunning) {
        await checkFarm();
        if (!farmLoopRunning) break;
        await sleep(CONFIG.farmCheckInterval); // 恢复固定间隔，无随机
    }
}

function startFarmCheckLoop() {
    if (farmLoopRunning) return;
    farmLoopRunning = true;
    networkEvents.on('landsChanged', onLandsChangedPush);
    farmCheckTimer = setTimeout(() => farmCheckLoop(), 2000);
}

let lastPushTime = 0;
function onLandsChangedPush(lands) {
    if (isCheckingFarm) return;
    const now = Date.now();
    if (now - lastPushTime < 500) return; // 轻微防抖
    lastPushTime = now;
    log('农场', `收到推送: ${lands.length}块变化，检查中...`);
    setTimeout(async () => {
        if (!isCheckingFarm) await checkFarm();
    }, 1000); // 推送后 1 秒检查
}

function stopFarmCheckLoop() {
    farmLoopRunning = false;
    if (farmCheckTimer) {
        clearTimeout(farmCheckTimer);
        farmCheckTimer = null;
    }
    networkEvents.removeListener('landsChanged', onLandsChangedPush);
}

module.exports = {
    checkFarm,
    startFarmCheckLoop,
    stopFarmCheckLoop,
    getCurrentPhase,
    setOperationLimitsCallback,
};