# -*- coding: utf-8 -*-
"""
库存管理路由

处理库存快照查询、库存概览、库存事务创建和查询。
"""

import logging
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import (
    NotFoundException,
    BadRequestException,
    InventoryException,
)
from app.crud.inventory import inventory_crud
from app.crud.product import product_crud
from app.models.user import User
from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    InventorySnapshotResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    InventoryOverviewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["库存管理"])


# ==================== 快照路由 ====================

@router.get(
    "/snapshots",
    response_model=PaginatedResponse[InventorySnapshotResponse],
    summary="获取库存快照列表",
)
async def get_snapshots(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    product_id: int | None = Query(default=None, description="产品ID筛选"),
    warehouse_id: int | None = Query(default=None, description="仓库ID筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[InventorySnapshotResponse]:
    """
    获取库存快照列表

    支持按产品ID和仓库ID筛选，支持分页。
    """
    skip = (page - 1) * page_size
    items, total = await inventory_crud.get_snapshots(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        skip=skip,
        limit=page_size,
    )

    return PaginatedResponse.create(
        items=[InventorySnapshotResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/snapshots/latest",
    response_model=list[InventorySnapshotResponse],
    summary="获取所有产品的最新库存快照",
)
async def get_latest_snapshots(
    warehouse_id: int | None = Query(default=None, description="仓库ID筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[InventorySnapshotResponse]:
    """
    获取所有产品的最新库存快照

    每个产品返回其在每个仓库的最新库存记录。
    """
    # 使用子查询获取每个 (product_id, warehouse_id) 的最新快照
    latest_subq = (
        select(
            InventorySnapshot.product_id,
            InventorySnapshot.warehouse_id,
            func.max(InventorySnapshot.id).label("max_id"),
        )
        .group_by(InventorySnapshot.product_id, InventorySnapshot.warehouse_id)
        .subquery()
    )

    stmt = (
        select(InventorySnapshot)
        .join(
            latest_subq,
            and_(
                InventorySnapshot.id == latest_subq.c.max_id,
            ),
        )
    )

    if warehouse_id is not None:
        stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)

    stmt = stmt.order_by(InventorySnapshot.product_id)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return [InventorySnapshotResponse.model_validate(s) for s in items]


@router.get(
    "/snapshots/overview",
    response_model=InventoryOverviewResponse,
    summary="获取库存概览",
)
async def get_inventory_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InventoryOverviewResponse:
    """
    获取库存概览统计信息

    包括：产品总数、仓库总数、库存总价值、低库存/缺货/超库存产品数、今日事务统计。
    """
    # 产品总数
    total_products = await product_crud.count(db)

    # 仓库总数
    from app.crud.base import BaseCRUD
    from app.models.warehouse import Warehouse
    wh_crud = BaseCRUD(Warehouse)
    total_warehouses = await wh_crud.count(db)

    # 库存总价值 - 基于最新快照
    latest_subq = (
        select(
            InventorySnapshot.product_id,
            InventorySnapshot.warehouse_id,
            func.max(InventorySnapshot.id).label("max_id"),
        )
        .group_by(InventorySnapshot.product_id, InventorySnapshot.warehouse_id)
        .subquery()
    )

    value_stmt = (
        select(func.coalesce(func.sum(InventorySnapshot.total_value), 0))
        .join(latest_subq, InventorySnapshot.id == latest_subq.c.max_id)
    )
    value_result = await db.execute(value_stmt)
    total_value = value_result.scalar() or Decimal("0.00")

    # 低库存产品数（库存量 <= min_stock）
    low_stock_stmt = (
        select(func.count(func.distinct(InventorySnapshot.product_id)))
        .join(latest_subq, InventorySnapshot.id == latest_subq.c.max_id)
        .join(Product, InventorySnapshot.product_id == Product.id)
        .where(InventorySnapshot.quantity <= Product.min_stock)
        .where(InventorySnapshot.quantity > 0)
    )
    low_stock_result = await db.execute(low_stock_stmt)
    low_stock_count = low_stock_result.scalar() or 0

    # 缺货产品数（库存量 == 0）
    out_of_stock_stmt = (
        select(func.count(func.distinct(InventorySnapshot.product_id)))
        .join(latest_subq, InventorySnapshot.id == latest_subq.c.max_id)
        .where(InventorySnapshot.quantity == 0)
    )
    oos_result = await db.execute(out_of_stock_stmt)
    out_of_stock_count = oos_result.scalar() or 0

    # 超库存产品数（库存量 >= max_stock 且 max_stock > 0）
    over_stock_stmt = (
        select(func.count(func.distinct(InventorySnapshot.product_id)))
        .join(latest_subq, InventorySnapshot.id == latest_subq.c.max_id)
        .join(Product, InventorySnapshot.product_id == Product.id)
        .where(InventorySnapshot.quantity >= Product.max_stock)
        .where(Product.max_stock > 0)
    )
    over_stock_result = await db.execute(over_stock_stmt)
    over_stock_count = over_stock_result.scalar() or 0

    # 今日事务统计
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    today_total_stmt = (
        select(func.count())
        .select_from(InventoryTransaction)
        .where(InventoryTransaction.created_at >= today_start)
    )
    today_total_result = await db.execute(today_total_stmt)
    total_transactions_today = today_total_result.scalar() or 0

    today_inbound_stmt = (
        select(func.count())
        .select_from(InventoryTransaction)
        .where(InventoryTransaction.transaction_type == "inbound")
        .where(InventoryTransaction.created_at >= today_start)
    )
    inbound_result = await db.execute(today_inbound_stmt)
    inbound_today = inbound_result.scalar() or 0

    today_outbound_stmt = (
        select(func.count())
        .select_from(InventoryTransaction)
        .where(InventoryTransaction.transaction_type == "outbound")
        .where(InventoryTransaction.created_at >= today_start)
    )
    outbound_result = await db.execute(today_outbound_stmt)
    outbound_today = outbound_result.scalar() or 0

    return InventoryOverviewResponse(
        total_products=total_products,
        total_warehouses=total_warehouses,
        total_value=total_value,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        over_stock_count=over_stock_count,
        total_transactions_today=total_transactions_today,
        inbound_today=inbound_today,
        outbound_today=outbound_today,
    )


# ==================== 事务路由 ====================

@router.post(
    "/transactions",
    response_model=InventoryTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建库存事务",
)
async def create_transaction(
    tx_in: InventoryTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InventoryTransactionResponse:
    """
    创建库存事务（入库/出库/调整/调拨）

    - 验证产品和仓库是否存在
    - 计算变动前后库存量
    - 创建事务记录并更新库存快照
    """
    # 验证产品存在
    product = await product_crud.get(db, id=tx_in.product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {tx_in.product_id}) 不存在")

    # 验证仓库存在
    from app.crud.base import BaseCRUD
    from app.models.warehouse import Warehouse
    wh_crud = BaseCRUD(Warehouse)
    warehouse = await wh_crud.get(db, id=tx_in.warehouse_id)
    if not warehouse:
        raise NotFoundException(detail=f"仓库 (ID: {tx_in.warehouse_id}) 不存在")

    # 获取当前库存
    current_snapshot = await inventory_crud.get_latest_snapshot(
        db,
        product_id=tx_in.product_id,
        warehouse_id=tx_in.warehouse_id,
    )
    current_quantity = current_snapshot.quantity if current_snapshot else 0

    # 计算新库存
    if tx_in.transaction_type == "inbound":
        new_quantity = current_quantity + tx_in.quantity
    elif tx_in.transaction_type == "outbound":
        if current_quantity < tx_in.quantity:
            raise InventoryException(
                detail=f"库存不足: 当前库存 {current_quantity}，需要出库 {tx_in.quantity}",
            )
        new_quantity = current_quantity - tx_in.quantity
    elif tx_in.transaction_type == "adjustment":
        new_quantity = tx_in.quantity  # 调整时 quantity 为调整后的目标值
    elif tx_in.transaction_type == "transfer":
        # 调拨：从当前仓库出库
        if current_quantity < tx_in.quantity:
            raise InventoryException(
                detail=f"调拨库存不足: 当前库存 {current_quantity}，需要调拨 {tx_in.quantity}",
            )
        new_quantity = current_quantity - tx_in.quantity
    else:
        raise BadRequestException(
            detail=f"无效的事务类型: {tx_in.transaction_type}，"
                   f"有效值为: inbound/outbound/adjustment/transfer",
        )

    # 创建事务记录
    tx_data = tx_in.model_dump()
    tx_data["previous_quantity"] = current_quantity
    tx_data["new_quantity"] = new_quantity
    tx_data["operator_id"] = current_user.id

    transaction = await inventory_crud.create_transaction(db, obj_in=tx_data)

    # 更新/创建库存快照
    unit_cost = float(product.cost_price)
    snapshot_data = {
        "product_id": tx_in.product_id,
        "warehouse_id": tx_in.warehouse_id,
        "quantity": new_quantity,
        "unit_cost": unit_cost,
        "total_value": unit_cost * new_quantity,
    }
    await inventory_crud.create_snapshot(db, obj_in=snapshot_data)

    # 如果是调拨，在目标仓库创建入库事务
    if tx_in.transaction_type == "transfer" and tx_in.to_warehouse_id:
        target_wh = await wh_crud.get(db, id=tx_in.to_warehouse_id)
        if not target_wh:
            raise NotFoundException(detail=f"目标仓库 (ID: {tx_in.to_warehouse_id}) 不存在")

        target_snapshot = await inventory_crud.get_latest_snapshot(
            db,
            product_id=tx_in.product_id,
            warehouse_id=tx_in.to_warehouse_id,
        )
        target_current = target_snapshot.quantity if target_snapshot else 0
        target_new = target_current + tx_in.quantity

        # 目标仓库入库事务
        await inventory_crud.create_transaction(db, obj_in={
            "product_id": tx_in.product_id,
            "warehouse_id": tx_in.to_warehouse_id,
            "transaction_type": "inbound",
            "quantity": tx_in.quantity,
            "previous_quantity": target_current,
            "new_quantity": target_new,
            "reference_no": tx_in.reference_no,
            "from_warehouse_id": tx_in.warehouse_id,
            "operator_id": current_user.id,
            "notes": f"调拨入库，来源仓库ID: {tx_in.warehouse_id}",
        })

        # 更新目标仓库快照
        await inventory_crud.create_snapshot(db, obj_in={
            "product_id": tx_in.product_id,
            "warehouse_id": tx_in.to_warehouse_id,
            "quantity": target_new,
            "unit_cost": unit_cost,
            "total_value": unit_cost * target_new,
        })

    logger.info(
        f"库存事务创建成功: 类型={tx_in.transaction_type}, "
        f"产品ID={tx_in.product_id}, 仓库ID={tx_in.warehouse_id}, "
        f"数量={tx_in.quantity}, 操作人ID={current_user.id}",
    )

    return InventoryTransactionResponse.model_validate(transaction)


@router.get(
    "/transactions",
    response_model=PaginatedResponse[InventoryTransactionResponse],
    summary="获取库存事务列表",
)
async def get_transactions(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    product_id: int | None = Query(default=None, description="产品ID筛选"),
    warehouse_id: int | None = Query(default=None, description="仓库ID筛选"),
    transaction_type: str | None = Query(default=None, description="事务类型筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[InventoryTransactionResponse]:
    """
    获取库存事务列表

    支持按产品ID、仓库ID和事务类型筛选，支持分页。
    """
    skip = (page - 1) * page_size
    items, total = await inventory_crud.get_transactions(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        transaction_type=transaction_type,
        skip=skip,
        limit=page_size,
    )

    return PaginatedResponse.create(
        items=[InventoryTransactionResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )
