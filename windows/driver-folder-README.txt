UWCC Control Center (open-uniwill-cc) - folder for the OEM driver
==================================================================

The free build of UWCC Control Center does not contain the original OEM driver
and is distributed completely freely (open source, MIT licence). Without the
driver it reaches the embedded controller through the open WMI implementation
(beta: slower, no liquid-cooling power boost, approximate power limits).

Recommended: put the OEM driver of the laptop manufacturer's Control Center
into this folder:

    UWACPIDriver.inf
    UWACPIDriver.sys
    UWACPIDriver.cat

then open Control Center -> EC Manager -> "Install the OEM driver"
(or run "uwccctl ec install-driver" as administrator).
By installing it you confirm that you have the right to use this file.

-----------------------------------------------------------------------------

Папка для OEM-драйвера

Свободная сборка UWCC Control Center не содержит оригинального OEM-драйвера
и распространяется полностью свободно (открытый код, лицензия MIT). Без
драйвера программа работает с встроенным контроллером через открытую
реализацию WMI (бета: медленнее, нет повышенной мощности с СЖО, пределы
мощности примерные).

Рекомендуем положить в эту папку OEM-драйвер из Control Center производителя
ноутбука:

    UWACPIDriver.inf
    UWACPIDriver.sys
    UWACPIDriver.cat

затем открыть Control Center -> Менеджер EC -> «Установить OEM-драйвер»
(или выполнить "uwccctl ec install-driver" от имени администратора).
Устанавливая драйвер, вы подтверждаете, что у вас есть право его использовать.
