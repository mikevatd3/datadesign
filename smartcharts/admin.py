from django.contrib import admin
from adminsortable2.admin import SortableTabularInline, SortableAdminBase
from .models import (
    DataPoint,
    StatList,
    ColumnChart,
    GroupedColumnChart,
    DoughnutChart,
    Row,
    RowItem,
    Section,
    Profile,
)


@admin.register(DataPoint)
class DataPointAdmin(admin.ModelAdmin):
    pass


@admin.register(StatList)
class StatListAdmin(admin.ModelAdmin):
    pass


@admin.register(ColumnChart)
class ColumnChartAdmin(admin.ModelAdmin):
    pass


@admin.register(DoughnutChart)
class DoughnutChartAdmin(admin.ModelAdmin):
    pass


@admin.register(GroupedColumnChart)
class GroupedColumnChartAdmin(admin.ModelAdmin):
    pass


class DesignInline(SortableTabularInline):
    model = RowItem
    extra = 0


@admin.register(Row)
class RowAdmin(SortableAdminBase, admin.ModelAdmin):
    exclude = ("order",)
    inlines = [DesignInline]
    list_filter = ("section",)


class RowInline(SortableTabularInline):
    model = Row
    extra = 0


@admin.register(Section)
class SectionAdmin(SortableAdminBase, admin.ModelAdmin):
    list_display = ("title", "num_rows")
    exclude = ("order",)
    inlines = [RowInline]
    
    def num_rows(self, obj):
        return Row.objects.filter(section=obj).count()


class SectionInline(SortableTabularInline):
    model = Section
    extra = 0


@admin.register(Profile)
class ProfileAdmin(SortableAdminBase, admin.ModelAdmin):
    inlines = [SectionInline]

