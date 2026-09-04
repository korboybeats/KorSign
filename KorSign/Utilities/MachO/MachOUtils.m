// Mach-O patching derived from LiveContainer (Apache-2.0).
// https://github.com/LiveContainer/LiveContainer/commit/3a029b6bb36c11cc05784a8840d41c7e46af1540
#import "MachOUtils.h"
#include <stddef.h>

#define SDK_VERSION_26_0_0 0x1A0000

static BOOL Fits(size_t offset, size_t length, size_t size) {
	return offset <= size && length <= size - offset;
}

// Read structs with memcpy: archive-provided offsets need not be naturally aligned.
static NSString *CollectSlice(const uint8_t *bytes, size_t offset, size_t size,
	BOOL sdk, BOOL arm64e, NSMutableDictionary<NSNumber *, NSNumber *> *patches) {
	if (size < sizeof(uint32_t)) return @"Truncated Mach-O magic";
	uint32_t magic;
	memcpy(&magic, bytes + offset, sizeof(magic));
	if (arm64e && magic != MH_MAGIC_64) return @"ARM64e entry requires a native 64-bit header";
	if (magic == MH_MAGIC || magic == MH_CIGAM || magic == MH_CIGAM_64) {
		// These architectures are not targets of either patch.
		size_t headerSize = magic == MH_CIGAM_64 ? sizeof(struct mach_header_64) : sizeof(struct mach_header);
		return size < headerSize ? @"Truncated Mach-O header" : nil;
	}
	if (magic != MH_MAGIC_64 || size < sizeof(struct mach_header_64)) return @"Invalid or truncated Mach-O header";
	struct mach_header_64 header;
	memcpy(&header, bytes + offset, sizeof(header));
	if (!Fits(sizeof(header), header.sizeofcmds, size) ||
		header.ncmds > header.sizeofcmds / sizeof(struct load_command)) return @"Invalid load-command region";

	size_t cursor = sizeof(header);
	size_t end = cursor + header.sizeofcmds;
	for (uint32_t i = 0; i < header.ncmds; i++) {
		if (!Fits(cursor, sizeof(struct load_command), end)) return @"Truncated load command";
		struct load_command command;
		memcpy(&command, bytes + offset + cursor, sizeof(command));
		if (command.cmdsize < sizeof(command) || command.cmdsize % 8 != 0 ||
			!Fits(cursor, command.cmdsize, end)) return @"Invalid load-command size";
		if (command.cmd == LC_BUILD_VERSION) {
			if (command.cmdsize < sizeof(struct build_version_command)) return @"Truncated build-version command";
			struct build_version_command build;
			memcpy(&build, bytes + offset + cursor, sizeof(build));
			if (build.ntools > (command.cmdsize - sizeof(build)) / sizeof(struct build_tool_version)) return @"Truncated build-tool list";
			if (sdk) patches[@(offset + cursor + offsetof(struct build_version_command, sdk))] = @(SDK_VERSION_26_0_0);
		}
		cursor += command.cmdsize;
	}
	if (cursor != end) return @"Load-command count does not match its region";
	if (arm64e) {
		if (header.cputype != CPU_TYPE_ARM64 || header.cpusubtype != CPU_SUBTYPE_ARM64E) return @"ARM64e slice does not match its architecture entry";
		patches[@(offset + offsetof(struct mach_header_64, cpusubtype))] = @((uint32_t)header.cpusubtype | CPU_SUBTYPE_LIB64);
	}
	return nil;
}

static NSString *CollectPatches(const uint8_t *bytes, size_t size, BOOL sdk,
	NSMutableDictionary<NSNumber *, NSNumber *> *patches) {
	if (size < sizeof(uint32_t)) return @"Truncated binary";
	uint32_t magic;
	memcpy(&magic, bytes, sizeof(magic));
	if (magic != FAT_MAGIC && magic != FAT_CIGAM) {
		return CollectSlice(bytes, 0, size, sdk, NO, patches);
	}
	if (size < sizeof(struct fat_header)) return @"Truncated universal header";
	struct fat_header header;
	memcpy(&header, bytes, sizeof(header));
	BOOL swap = magic == FAT_CIGAM;
	uint32_t count = swap ? OSSwapInt32(header.nfat_arch) : header.nfat_arch;
	if (count == 0 || count > (size - sizeof(header)) / sizeof(struct fat_arch)) return @"Invalid architecture table";
	size_t tableSize = sizeof(header) + count * sizeof(struct fat_arch);
	NSMutableIndexSet *occupied = [NSMutableIndexSet indexSetWithIndexesInRange:NSMakeRange(0, tableSize)];
	for (uint32_t i = 0; i < count; i++) {
		size_t entryOffset = sizeof(header) + i * sizeof(struct fat_arch);
		struct fat_arch arch;
		memcpy(&arch, bytes + entryOffset, sizeof(arch));
		size_t offset = swap ? OSSwapInt32(arch.offset) : arch.offset;
		size_t length = swap ? OSSwapInt32(arch.size) : arch.size;
		uint32_t cpu = swap ? OSSwapInt32(arch.cputype) : arch.cputype;
		uint32_t subtype = swap ? OSSwapInt32(arch.cpusubtype) : arch.cpusubtype;
		if (length == 0 || !Fits(offset, length, size)) return @"Invalid slice extent";
		NSRange range = NSMakeRange(offset, length);
		if ([occupied intersectsIndexesInRange:range]) return @"Overlapping architecture slices";
		[occupied addIndexesInRange:range];
		BOOL arm64e = !sdk && cpu == CPU_TYPE_ARM64 && subtype == CPU_SUBTYPE_ARM64E;
		NSString *error = CollectSlice(bytes, offset, length, sdk, arm64e, patches);
		if (error) return error;
		if (arm64e) {
			uint32_t value = subtype | CPU_SUBTYPE_LIB64;
			patches[@(entryOffset + offsetof(struct fat_arch, cpusubtype))] = @(swap ? OSSwapInt32(value) : value);
		}
	}
	return nil;
}

static NSString *PatchFile(const char *path, BOOL sdk) {
	int fd = open(path, O_RDWR);
	if (fd < 0) return [NSString stringWithFormat:@"Failed to open binary: %s", strerror(errno)];
	struct stat info;
	if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < sizeof(uint32_t) || (uint64_t)info.st_size > SIZE_MAX) {
		close(fd);
		return @"Invalid or truncated binary file";
	}
	size_t size = (size_t)info.st_size;
	void *map = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	if (map == MAP_FAILED) {
		NSString *error = [NSString stringWithFormat:@"Failed to map binary: %s", strerror(errno)];
		close(fd);
		return error;
	}
	NSMutableDictionary<NSNumber *, NSNumber *> *patches = [NSMutableDictionary dictionary];
	NSString *error = CollectPatches(map, size, sdk, patches);
	// No mutation until every slice and command has passed validation.
	if (!error) {
		for (NSNumber *location in patches) {
			uint32_t value = patches[location].unsignedIntValue;
			memcpy((uint8_t *)map + location.unsignedLongLongValue, &value, sizeof(value));
		}
		if (patches.count && msync(map, size, MS_SYNC) != 0) error = [NSString stringWithFormat:@"Failed to flush binary: %s", strerror(errno)];
	}
	munmap(map, size);
	close(fd);
	return error;
}

NSString *LCPatchMachOFixupARM64eSlice(const char *path) { return PatchFile(path, NO); }
NSString *LCPatchMachOForSDK26(const char *path) { return PatchFile(path, YES); }
