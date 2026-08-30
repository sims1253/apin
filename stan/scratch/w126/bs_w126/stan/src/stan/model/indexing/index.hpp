#ifndef STAN_MODEL_INDEXING_INDEX_HPP
#define STAN_MODEL_INDEXING_INDEX_HPP

#include <stan/math/prim/meta.hpp>
#include <cstddef>
#include <utility>
#include <vector>

namespace stan {

namespace model {

namespace internal {
/**
 * Read-only view of the storage of a sequence of multiple indexes.
 *
 * When constructed from an rvalue index vector, the view takes ownership
 * of the vector (moving its storage). When constructed from an lvalue
 * index vector, the view refers to the caller's storage without copying
 * it, so that indexing a container with model-data index arrays does not
 * deep-copy the (immutable) index array on every use. The caller must
 * keep an lvalue-referenced vector alive as long as the view is used.
 *
 * A copy of a view always takes ownership of a copy of the indexed
 * values, so a copy never depends on the lifetime of the original.
 */
class multi_index_view {
 public:
  using size_type = std::size_t;
  using const_iterator = const int*;

  /**
   * Construct a view of (without copying) an lvalue index vector.
   * @param ns multiple indexes.
   */
  multi_index_view(const std::vector<int>& ns) noexcept
      : ptr_(ns.data()), size_(ns.size()) {}

  /**
   * Construct a view taking ownership of an rvalue index vector's
   * storage.
   * @param ns multiple indexes.
   */
  multi_index_view(std::vector<int>&& ns) noexcept
      : owned_(std::move(ns)) {
    ptr_ = owned_.data();
    size_ = owned_.size();
  }

  /**
   * Construct a view of a copy of an index vector with a non-`int`
   * integral value type (its values are converted to `int`).
   * @tparam T a standard vector with integral value type.
   * @param ns multiple indexes.
   */
  template <typename T, require_std_vector_vt<std::is_integral, T>* = nullptr,
            require_not_same_t<value_type_t<T>, int>* = nullptr>
  multi_index_view(const T& ns) : owned_(ns.begin(), ns.end()) {
    ptr_ = owned_.data();
    size_ = owned_.size();
  }

  /**
   * Copy constructor; always takes ownership of a copy of the viewed
   * values.
   * @param other view to copy.
   */
  multi_index_view(const multi_index_view& other) : owned_() {
    if (other.size_ != 0) {
      owned_.assign(other.ptr_, other.ptr_ + other.size_);
      ptr_ = owned_.data();
    } else {
      ptr_ = other.ptr_;
    }
    size_ = other.size_;
  }

  /**
   * Move constructor; keeps the storage relationship of the original.
   * @param other view to move from.
   */
  multi_index_view(multi_index_view&& other) noexcept
      : owned_(std::move(other.owned_)) {
    if (!owned_.empty()) {
      ptr_ = owned_.data();
      size_ = owned_.size();
    } else {
      ptr_ = other.ptr_;
      size_ = other.size_;
    }
    other.ptr_ = nullptr;
    other.size_ = 0;
  }

  /**
   * Copy assignment; takes ownership of a copy of the right-hand side's
   * viewed values.
   * @param other view to copy.
   * @return this view
   */
  multi_index_view& operator=(const multi_index_view& other) {
    if (this != &other) {
      owned_.clear();
      if (other.size_ != 0) {
        owned_.assign(other.ptr_, other.ptr_ + other.size_);
        ptr_ = owned_.data();
      } else {
        ptr_ = other.ptr_;
      }
      size_ = other.size_;
    }
    return *this;
  }

  /**
   * Move assignment; keeps the storage relationship of the right-hand
   * side.
   * @param other view to move from.
   * @return this view
   */
  multi_index_view& operator=(multi_index_view&& other) noexcept {
    if (this != &other) {
      owned_ = std::move(other.owned_);
      if (!owned_.empty()) {
        ptr_ = owned_.data();
        size_ = owned_.size();
      } else {
        ptr_ = other.ptr_;
        size_ = other.size_;
      }
      other.ptr_ = nullptr;
      other.size_ = 0;
    }
    return *this;
  }

  /**
   * Return a pointer to the first viewed index.
   * @return pointer to first index
   */
  const int* data() const noexcept { return ptr_; }

  /**
   * Return the number of viewed indexes.
   * @return number of indexes
   */
  size_type size() const noexcept { return size_; }

  /**
   * Return whether no indexes are viewed.
   * @return whether empty
   */
  bool empty() const noexcept { return size_ == 0; }

  /**
   * Return an iterator to the first viewed index.
   * @return begin iterator
   */
  const_iterator begin() const noexcept { return ptr_; }

  /**
   * Return an iterator past the last viewed index.
   * @return end iterator
   */
  const_iterator end() const noexcept { return ptr_ + size_; }

  /**
   * Return the viewed index at the specified position.
   * @param n position
   * @return index at position
   */
  int operator[](size_type n) const noexcept { return ptr_[n]; }

 private:
  /**
   * Owned index storage; empty when this view refers to caller-owned
   * storage.
   */
  std::vector<int> owned_;
  const int* ptr_;
  std::size_t size_;
};
}  // namespace internal

// SINGLE INDEXING (reduces dimensionality)

/**
 * Structure for an indexing consisting of a single index.
 * Applying this index reduces the dimensionality of the container
 * to which it is applied by one.
 */
struct index_uni {
  int n_;

  /**
   * Construct a single indexing from the specified index.
   *
   * @param n single index.
   */
  constexpr explicit index_uni(int n) noexcept : n_(n) {}
};

// MULTIPLE INDEXING (does not reduce dimensionality)

/**
 * Structure for an indexing consisting of multiple indexes.  The
 * indexes do not need to be unique or in order.
 */
struct index_multi {
  internal::multi_index_view ns_;

  /**
   * Construct a multiple indexing from the specified indexes.  The
   * index vector's storage is viewed without copying when it is an
   * lvalue (it must then outlive the uses of this indexing), and moved
   * into the indexing when it is an rvalue.
   *
   * @param ns multiple indexes.
   */
  template <typename T, require_std_vector_vt<std::is_integral, T>* = nullptr>
  explicit index_multi(T&& ns) noexcept(
      std::is_nothrow_constructible_v<internal::multi_index_view, T>)
      : ns_(std::forward<T>(ns)) {}
};

/**
 * Structure for an indexing that consists of all indexes for a
 * container.  Applying this index is a no-op.
 */
struct index_omni {};

/**
 * Structure for an indexing from a minimum index (inclusive) to
 * the end of a container.
 */
struct index_min {
  int min_;

  /**
   * Construct an indexing from the specified minimum index (inclusive).
   *
   * @param min minimum index (inclusive).
   */
  constexpr explicit index_min(int min) noexcept : min_(min) {}
};

/**
 * Structure for an indexing from the start of a container to a
 * specified maximum index (inclusive).
 */
struct index_max {
  int max_;

  /**
   * Construct an indexing from the start of the container up to
   * the specified maximum index (inclusive).
   *
   * @param max maximum index (inclusive).
   */
  constexpr explicit index_max(int max) noexcept : max_(max) {}
};

/**
 * Structure for an indexing from a minimum index (inclusive) to a
 * maximum index (inclusive).
 */
struct index_min_max {
  int min_;
  int max_;
  /**
   * Return whether the index is positive or negative
   */
  inline bool is_ascending() const noexcept { return min_ <= max_; }
  /**
   * Construct an indexing from the specified minimum index
   * (inclusive) and maximum index (inclusive).
   *
   * @param min minimum index (inclusive).
   * @param max maximum index (inclusive).
   */
  constexpr index_min_max(int min, int max) noexcept : min_(min), max_(max) {}
};

}  // namespace model
}  // namespace stan
#endif
