// SPDX-License-Identifier: GPL-2.0
/*
 * uwcc — EC access + hot-key events for Uniwill/Tongfang laptops (Control Center for Linux)
 *
 * /dev/uwcc
 *   ioctl UWCC_IOC_READ / UWCC_IOC_WRITE : evaluates the firmware methods
 *       \_SB.INOU.ECRR(addr) / ECRW(addr, data) of ACPI device INOU0000, i.e. the same
 *       methods the Windows UWACPIDriver.sys calls for GCUService.
 *   ioctl UWCC_IOC_SMRW : evaluates \_SB.INOU.SMRW(Buffer{0xBB, key, 0, 0}) — the "Smart APC"
 *       limit table (PL1/PL2/PL4/TCC/cTGP/Dynamic Boost), UWACPIDriver IOCTL 0x9C40A500.
 *   read()/poll() : 32-bit event codes from the WMI event "AcpiTest_EventULong"
 *       (0xB0 mode key, 0xA7 fan boost, 0x40/0x41 Win-lock, 0xB8 Fn-lock, ...).
 */
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/acpi.h>
#include <linux/fs.h>
#include <linux/kfifo.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/poll.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/wait.h>
#include <linux/wmi.h>

#define UWCC_HID "INOU0000"

struct uwcc_ec {
	__u16 addr;
	__u16 data;
};

struct uwcc_smrw {
	__u8 in[4];
	__u8 out[4];
};

#define UWCC_IOC_READ  _IOWR('u', 1, struct uwcc_ec)
#define UWCC_IOC_WRITE _IOW('u', 2, struct uwcc_ec)
#define UWCC_IOC_SMRW  _IOWR('u', 3, struct uwcc_smrw)

static acpi_handle inou_handle;
static DEFINE_MUTEX(ec_lock);
static DEFINE_SPINLOCK(ev_lock);
static DECLARE_KFIFO(ev_fifo, u32, 64);
static DECLARE_WAIT_QUEUE_HEAD(ev_wait);
static int wmi_bound;
static bool wmi_registered;

/* ------------------------------------------------------------------ EC */

static int uwcc_ec_read(u16 addr, u8 *val)
{
	union acpi_object arg;
	struct acpi_object_list args = { .count = 1, .pointer = &arg };
	unsigned long long out = 0;
	acpi_status st;

	if (!inou_handle)
		return -ENODEV;
	arg.type = ACPI_TYPE_INTEGER;
	arg.integer.value = addr;
	mutex_lock(&ec_lock);
	st = acpi_evaluate_integer(inou_handle, "ECRR", &args, &out);
	mutex_unlock(&ec_lock);
	if (ACPI_FAILURE(st))
		return -EIO;
	*val = out & 0xff;
	return 0;
}

static int uwcc_ec_write(u16 addr, u8 val)
{
	union acpi_object arg[2];
	struct acpi_object_list args = { .count = 2, .pointer = arg };
	acpi_status st;

	if (!inou_handle)
		return -ENODEV;
	arg[0].type = ACPI_TYPE_INTEGER;
	arg[0].integer.value = addr;
	arg[1].type = ACPI_TYPE_INTEGER;
	arg[1].integer.value = val;
	mutex_lock(&ec_lock);
	st = acpi_evaluate_object(inou_handle, "ECRW", &args, NULL);
	mutex_unlock(&ec_lock);
	return ACPI_FAILURE(st) ? -EIO : 0;
}

static int uwcc_smrw(struct uwcc_smrw *r)
{
	union acpi_object arg, *obj;
	struct acpi_object_list args = { .count = 1, .pointer = &arg };
	struct acpi_buffer out = { ACPI_ALLOCATE_BUFFER, NULL };
	acpi_status st;
	int ret = -EIO;

	if (!inou_handle || !acpi_has_method(inou_handle, "SMRW"))
		return -ENODEV;
	arg.type = ACPI_TYPE_BUFFER;
	arg.buffer.length = sizeof(r->in);
	arg.buffer.pointer = r->in;
	mutex_lock(&ec_lock);
	st = acpi_evaluate_object(inou_handle, "SMRW", &args, &out);
	mutex_unlock(&ec_lock);
	if (ACPI_FAILURE(st))
		return -EIO;
	obj = out.pointer;
	memset(r->out, 0, sizeof(r->out));
	if (obj && obj->type == ACPI_TYPE_BUFFER) {
		memcpy(r->out, obj->buffer.pointer, min_t(u32, obj->buffer.length, sizeof(r->out)));
		ret = 0;
	} else if (obj && obj->type == ACPI_TYPE_INTEGER) {
		u32 v = (u32)obj->integer.value;

		memcpy(r->out, &v, sizeof(r->out));
		ret = 0;
	}
	kfree(out.pointer);
	return ret;
}

static acpi_status uwcc_find_cb(acpi_handle handle, u32 level, void *ctx, void **ret)
{
	*ret = handle;
	return AE_CTRL_TERMINATE;
}

/* --------------------------------------------------------------- events */

static void uwcc_push(u32 code)
{
	unsigned long flags;

	spin_lock_irqsave(&ev_lock, flags);
	if (kfifo_is_full(&ev_fifo))
		kfifo_skip(&ev_fifo);
	kfifo_put(&ev_fifo, code);
	spin_unlock_irqrestore(&ev_lock, flags);
	wake_up_interruptible(&ev_wait);
}

static void uwcc_wmi_notify(struct wmi_device *wdev, union acpi_object *obj)
{
	u32 code;

	if (!obj)
		return;
	if (obj->type == ACPI_TYPE_INTEGER)
		code = (u32)obj->integer.value;
	else if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 4) {
		__le32 le;

		memcpy(&le, obj->buffer.pointer, sizeof(le));
		code = le32_to_cpu(le);
	} else if (obj->type == ACPI_TYPE_BUFFER && obj->buffer.length >= 1)
		code = obj->buffer.pointer[0];
	else
		return;
	uwcc_push(code);
}

static int uwcc_wmi_probe(struct wmi_device *wdev, const void *context)
{
	dev_info(&wdev->dev, "hot-key events bound\n");
	wmi_bound++;
	return 0;
}

static void uwcc_wmi_remove(struct wmi_device *wdev)
{
	wmi_bound--;
}

static const struct wmi_device_id uwcc_wmi_ids[] = {
	{ .guid_string = "ABBC0F72-8EA1-11D1-00A0-C90629100000" },
	{ .guid_string = "ABBC0F71-8EA1-11D1-00A0-C90629100000" },
	{ .guid_string = "ABBC0F70-8EA1-11D1-00A0-C90629100000" },
	{ }
};
MODULE_DEVICE_TABLE(wmi, uwcc_wmi_ids);

static struct wmi_driver uwcc_wmi_driver = {
	.driver = { .name = "uwcc-wmi" },
	.id_table = uwcc_wmi_ids,
	.probe = uwcc_wmi_probe,
	.remove = uwcc_wmi_remove,
	.notify = uwcc_wmi_notify,
};

/* ------------------------------------------------------------ chardev */

static ssize_t uwcc_read(struct file *f, char __user *buf, size_t len, loff_t *off)
{
	u32 codes[16];
	unsigned int n, want;
	unsigned long flags;
	int ret;

	if (len < sizeof(u32))
		return -EINVAL;
	for (;;) {
		want = min_t(size_t, len / sizeof(u32), ARRAY_SIZE(codes));
		spin_lock_irqsave(&ev_lock, flags);
		n = kfifo_out(&ev_fifo, codes, want);
		spin_unlock_irqrestore(&ev_lock, flags);
		if (n)
			break;
		if (f->f_flags & O_NONBLOCK)
			return -EAGAIN;
		ret = wait_event_interruptible(ev_wait, !kfifo_is_empty(&ev_fifo));
		if (ret)
			return ret;
	}
	if (copy_to_user(buf, codes, n * sizeof(u32)))
		return -EFAULT;
	return n * sizeof(u32);
}

static __poll_t uwcc_poll(struct file *f, poll_table *wait)
{
	poll_wait(f, &ev_wait, wait);
	return kfifo_is_empty(&ev_fifo) ? 0 : (EPOLLIN | EPOLLRDNORM);
}

static long uwcc_ioctl(struct file *f, unsigned int cmd, unsigned long arg)
{
	struct uwcc_ec req;
	struct uwcc_smrw sm;
	u8 v;
	int ret;

	if (!capable(CAP_SYS_RAWIO))
		return -EPERM;
	if (cmd == UWCC_IOC_SMRW) {
		if (copy_from_user(&sm, (void __user *)arg, sizeof(sm)))
			return -EFAULT;
		ret = uwcc_smrw(&sm);
		if (ret)
			return ret;
		return copy_to_user((void __user *)arg, &sm, sizeof(sm)) ? -EFAULT : 0;
	}
	if (copy_from_user(&req, (void __user *)arg, sizeof(req)))
		return -EFAULT;
	switch (cmd) {
	case UWCC_IOC_READ:
		ret = uwcc_ec_read(req.addr, &v);
		if (ret)
			return ret;
		req.data = v;
		return copy_to_user((void __user *)arg, &req, sizeof(req)) ? -EFAULT : 0;
	case UWCC_IOC_WRITE:
		return uwcc_ec_write(req.addr, req.data & 0xff);
	default:
		return -ENOTTY;
	}
}

static const struct file_operations uwcc_fops = {
	.owner = THIS_MODULE,
	.read = uwcc_read,
	.poll = uwcc_poll,
	.unlocked_ioctl = uwcc_ioctl,
	.compat_ioctl = uwcc_ioctl,
	.llseek = noop_llseek,
};

static struct miscdevice uwcc_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "uwcc",
	.fops = &uwcc_fops,
	.mode = 0600,
};

static int __init uwcc_init(void)
{
	void *h = NULL;
	int ret;

	INIT_KFIFO(ev_fifo);
	acpi_get_devices(UWCC_HID, uwcc_find_cb, NULL, &h);
	inou_handle = h;
	if (!inou_handle)
		pr_warn("ACPI device %s not found — EC access disabled\n", UWCC_HID);
	else if (!acpi_has_method(inou_handle, "ECRR") || !acpi_has_method(inou_handle, "ECRW")) {
		pr_warn("%s has no ECRR/ECRW — EC access disabled\n", UWCC_HID);
		inou_handle = NULL;
	}
	ret = misc_register(&uwcc_misc);
	if (ret)
		return ret;
	ret = wmi_driver_register(&uwcc_wmi_driver);
	if (ret)
		pr_warn("WMI driver registration failed (%d) — no hot-key events\n", ret);
	else
		wmi_registered = true;
	pr_info("loaded (EC %s)\n", inou_handle ? "ok" : "unavailable");
	return 0;
}

static void __exit uwcc_exit(void)
{
	if (wmi_registered)
		wmi_driver_unregister(&uwcc_wmi_driver);
	misc_deregister(&uwcc_misc);
}

module_init(uwcc_init);
module_exit(uwcc_exit);

MODULE_AUTHOR("Control Center for Linux");
MODULE_DESCRIPTION("Uniwill/Tongfang EC access and WMI hot-key events");
MODULE_LICENSE("GPL");
MODULE_ALIAS("acpi*:" UWCC_HID ":*");
